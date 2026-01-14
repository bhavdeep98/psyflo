"""Tests for CrisisHandler - safety-critical code requires 100% coverage."""
import pytest
from unittest.mock import Mock, patch

from feelwell.services.crisis_engine.handler import (
    CrisisHandler,
    CrisisState,
    CrisisRecord,
)
from feelwell.services.crisis_engine.events import (
    CrisisEventPublisher,
    EscalationPath,
)


@pytest.fixture
def mock_publisher():
    """Create a mock event publisher."""
    publisher = Mock(spec=CrisisEventPublisher)
    publisher.publish.return_value = True
    publisher.create_crisis_event.return_value = Mock(
        event_id="evt_test123",
        event_type="safety.crisis.detected",
    )
    return publisher


@pytest.fixture
def handler(mock_publisher):
    """Create a CrisisHandler with mock publisher."""
    return CrisisHandler(event_publisher=mock_publisher)


class TestSafetyCrisisHandling:
    """Tests for handling crises from Safety Service."""
    
    def test_safety_crisis_creates_record(self, handler):
        """Safety crisis should create a tracking record."""
        record = handler.handle_safety_crisis(
            student_id_hash="hash_abc123",
            session_id="sess_xyz",
            matched_keywords=["kill myself"],
            school_id="school_001",
        )
        
        assert record is not None
        assert record.student_id_hash == "hash_abc123"
        assert record.session_id == "sess_xyz"
        assert record.school_id == "school_001"
        assert record.trigger_source == "safety_service"
    
    def test_safety_crisis_publishes_event(self, handler, mock_publisher):
        """Safety crisis should publish event to stream."""
        handler.handle_safety_crisis(
            student_id_hash="hash_abc123",
            session_id="sess_xyz",
            matched_keywords=["kill myself"],
        )
        
        mock_publisher.publish.assert_called_once()
    
    def test_safety_crisis_state_transitions(self, handler):
        """Crisis should transition from DETECTED to NOTIFYING."""
        record = handler.handle_safety_crisis(
            student_id_hash="hash_abc123",
            session_id="sess_xyz",
            matched_keywords=["kill myself"],
        )
        
        assert record.state == CrisisState.NOTIFYING
    
    def test_safety_crisis_default_escalation_path(self, handler):
        """Default escalation should be COUNSELOR_ALERT."""
        record = handler.handle_safety_crisis(
            student_id_hash="hash_abc123",
            session_id="sess_xyz",
            matched_keywords=["kill myself"],
        )
        
        assert record.escalation_path == EscalationPath.COUNSELOR_ALERT


class TestObserverThresholdHandling:
    """Tests for handling threshold exceeded from Observer Service."""
    
    def test_observer_threshold_creates_record(self, handler):
        """Observer threshold should create a tracking record."""
        record = handler.handle_observer_threshold(
            student_id_hash="hash_def456",
            session_id="sess_abc",
            risk_score=0.85,
            phq9_score=15,
            school_id="school_002",
        )
        
        assert record is not None
        assert record.student_id_hash == "hash_def456"
        assert record.trigger_source == "observer_service"
    
    def test_observer_threshold_publishes_event(self, handler, mock_publisher):
        """Observer threshold should publish event to stream."""
        handler.handle_observer_threshold(
            student_id_hash="hash_def456",
            session_id="sess_abc",
            risk_score=0.85,
        )
        
        mock_publisher.publish.assert_called_once()


class TestCrisisAcknowledgment:
    """Tests for crisis acknowledgment flow."""
    
    def test_acknowledge_updates_state(self, handler):
        """Acknowledging crisis should update state."""
        record = handler.handle_safety_crisis(
            student_id_hash="hash_abc123",
            session_id="sess_xyz",
            matched_keywords=["kill myself"],
        )
        
        updated = handler.acknowledge(
            crisis_id=record.crisis_id,
            acknowledged_by="counselor_001",
        )
        
        assert updated.state == CrisisState.ACKNOWLEDGED
        assert updated.acknowledged_by == "counselor_001"
        assert updated.acknowledged_at is not None
    
    def test_acknowledge_nonexistent_returns_none(self, handler):
        """Acknowledging nonexistent crisis should return None."""
        result = handler.acknowledge(
            crisis_id="nonexistent_id",
            acknowledged_by="counselor_001",
        )
        
        assert result is None


class TestCrisisResolution:
    """Tests for crisis resolution flow."""
    
    def test_resolve_updates_state(self, handler):
        """Resolving crisis should update state."""
        record = handler.handle_safety_crisis(
            student_id_hash="hash_abc123",
            session_id="sess_xyz",
            matched_keywords=["kill myself"],
        )
        
        handler.acknowledge(
            crisis_id=record.crisis_id,
            acknowledged_by="counselor_001",
        )
        
        resolved = handler.resolve(
            crisis_id=record.crisis_id,
            resolved_by="counselor_001",
            resolution_notes="Student met with counselor, safety plan created",
        )
        
        assert resolved.state == CrisisState.RESOLVED
        assert resolved.resolved_by == "counselor_001"
        assert resolved.resolution_notes is not None
        assert resolved.resolved_at is not None
    
    def test_resolve_nonexistent_returns_none(self, handler):
        """Resolving nonexistent crisis should return None."""
        result = handler.resolve(
            crisis_id="nonexistent_id",
            resolved_by="counselor_001",
            resolution_notes="N/A",
        )
        
        assert result is None


class TestActiveCrisisTracking:
    """Tests for tracking active crises."""
    
    def test_get_active_crises_returns_unresolved(self, handler):
        """Should return only unresolved crises."""
        # Create two crises
        record1 = handler.handle_safety_crisis(
            student_id_hash="hash_001",
            session_id="sess_001",
            matched_keywords=["crisis"],
            school_id="school_001",
        )
        record2 = handler.handle_safety_crisis(
            student_id_hash="hash_002",
            session_id="sess_002",
            matched_keywords=["crisis"],
            school_id="school_001",
        )
        
        # Resolve one
        handler.acknowledge(record1.crisis_id, "counselor")
        handler.resolve(record1.crisis_id, "counselor", "resolved")
        
        active = handler.get_active_crises()
        
        assert len(active) == 1
        assert active[0].crisis_id == record2.crisis_id
    
    def test_get_active_crises_filters_by_school(self, handler):
        """Should filter by school_id when provided."""
        handler.handle_safety_crisis(
            student_id_hash="hash_001",
            session_id="sess_001",
            matched_keywords=["crisis"],
            school_id="school_001",
        )
        handler.handle_safety_crisis(
            student_id_hash="hash_002",
            session_id="sess_002",
            matched_keywords=["crisis"],
            school_id="school_002",
        )
        
        active = handler.get_active_crises(school_id="school_001")
        
        assert len(active) == 1
        assert active[0].school_id == "school_001"
