"""Tests for CrisisEventPublisher.

Per ADR-004: Crisis events publish to Kinesis, not direct service calls.
These tests verify the publisher correctly formats and sends events.
"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from feelwell.services.safety_service.crisis_publisher import (
    CrisisEventPublisher,
    SafetyCrisisEvent,
)


class TestSafetyCrisisEvent:
    """Tests for SafetyCrisisEvent dataclass."""
    
    def test_event_creation(self):
        """Event should be created with correct defaults."""
        event = SafetyCrisisEvent(
            event_id="evt_123",
            message_id="msg_456",
            session_id="sess_789",
            student_id_hash="hash_abc",
        )
        
        assert event.event_type == "safety.crisis.detected"
        assert event.risk_level == "CRISIS"
        assert event.risk_score == 1.0
        assert event.trigger_source == "safety_service"
        assert event.requires_human_intervention is True
        assert event.escalation_path == "counselor_alert"
    
    def test_event_to_kinesis_payload(self):
        """Event should convert to valid Kinesis payload."""
        event = SafetyCrisisEvent(
            event_id="evt_123",
            message_id="msg_456",
            session_id="sess_789",
            student_id_hash="hash_abc",
            school_id="school_001",
            matched_keywords=["kill myself"],
            scanner_version="2026.01.14",
        )
        
        payload = event.to_kinesis_payload()
        
        assert payload["event_id"] == "evt_123"
        assert payload["event_type"] == "safety.crisis.detected"
        assert payload["source"] == "safety-service"
        assert "timestamp" in payload
        assert payload["data"]["message_id"] == "msg_456"
        assert payload["data"]["session_id"] == "sess_789"
        assert payload["data"]["student_id_hash"] == "hash_abc"
        assert payload["data"]["school_id"] == "school_001"
        assert payload["data"]["matched_keywords"] == ["kill myself"]
    
    def test_event_is_immutable(self):
        """Event should be immutable (frozen dataclass)."""
        event = SafetyCrisisEvent(
            event_id="evt_123",
            message_id="msg_456",
            session_id="sess_789",
            student_id_hash="hash_abc",
        )
        
        with pytest.raises(Exception):  # FrozenInstanceError
            event.risk_level = "SAFE"


class TestCrisisEventPublisher:
    """Tests for CrisisEventPublisher."""
    
    def test_publisher_initialization(self):
        """Publisher should initialize with correct config."""
        publisher = CrisisEventPublisher(
            stream_name="test-stream",
            enabled=True,
            region="us-west-2",
        )
        
        assert publisher.stream_name == "test-stream"
        assert publisher.enabled is True
        assert publisher.region == "us-west-2"
    
    def test_publish_disabled_returns_false(self):
        """Publishing when disabled should return False."""
        publisher = CrisisEventPublisher(enabled=False)
        
        result = publisher.publish_crisis(
            message_id="msg_123",
            session_id="sess_456",
            student_id_hash="hash_abc",
            matched_keywords=["test"],
            risk_score=1.0,
            scanner_version="2026.01.14",
        )
        
        assert result is False
    
    @patch('boto3.client')
    def test_publish_success(self, mock_boto_client):
        """Successful publish should return True."""
        mock_kinesis = MagicMock()
        mock_kinesis.put_record.return_value = {
            "ShardId": "shard-001",
            "SequenceNumber": "12345",
        }
        mock_boto_client.return_value = mock_kinesis
        
        publisher = CrisisEventPublisher(
            stream_name="test-stream",
            enabled=True,
        )
        # Force client initialization
        publisher._kinesis_client = mock_kinesis
        
        result = publisher.publish_crisis(
            message_id="msg_123",
            session_id="sess_456",
            student_id_hash="hash_abc",
            matched_keywords=["kill myself"],
            risk_score=1.0,
            scanner_version="2026.01.14",
            school_id="school_001",
        )
        
        assert result is True
        mock_kinesis.put_record.assert_called_once()
        
        # Verify call arguments
        call_kwargs = mock_kinesis.put_record.call_args.kwargs
        assert call_kwargs["StreamName"] == "test-stream"
        assert call_kwargs["PartitionKey"] == "hash_abc"
        
        # Verify payload
        payload = json.loads(call_kwargs["Data"])
        assert payload["event_type"] == "safety.crisis.detected"
        assert payload["data"]["message_id"] == "msg_123"
        assert payload["data"]["school_id"] == "school_001"
    
    @patch('boto3.client')
    def test_publish_failure_returns_false(self, mock_boto_client):
        """Failed publish should return False, not raise."""
        mock_kinesis = MagicMock()
        mock_kinesis.put_record.side_effect = Exception("Kinesis error")
        mock_boto_client.return_value = mock_kinesis
        
        publisher = CrisisEventPublisher(
            stream_name="test-stream",
            enabled=True,
        )
        publisher._kinesis_client = mock_kinesis
        
        # Should NOT raise exception
        result = publisher.publish_crisis(
            message_id="msg_123",
            session_id="sess_456",
            student_id_hash="hash_abc",
            matched_keywords=["test"],
            risk_score=1.0,
            scanner_version="2026.01.14",
        )
        
        assert result is False
    
    def test_publish_without_client_logs_fallback(self):
        """Publishing without Kinesis client should log fallback."""
        publisher = CrisisEventPublisher(
            stream_name="test-stream",
            enabled=True,
        )
        # Client is None (not initialized)
        publisher._kinesis_client = None
        
        result = publisher.publish_crisis(
            message_id="msg_123",
            session_id="sess_456",
            student_id_hash="hash_abc",
            matched_keywords=["test"],
            risk_score=1.0,
            scanner_version="2026.01.14",
        )
        
        # Should return False but not crash
        assert result is False
    
    @patch('boto3.client')
    def test_publish_batch_success(self, mock_boto_client):
        """Batch publish should return count of successful records."""
        mock_kinesis = MagicMock()
        mock_kinesis.put_records.return_value = {
            "FailedRecordCount": 0,
            "Records": [{"ShardId": "shard-001"}, {"ShardId": "shard-001"}],
        }
        mock_boto_client.return_value = mock_kinesis
        
        publisher = CrisisEventPublisher(
            stream_name="test-stream",
            enabled=True,
        )
        publisher._kinesis_client = mock_kinesis
        
        events = [
            SafetyCrisisEvent(
                event_id="evt_1",
                message_id="msg_1",
                session_id="sess_1",
                student_id_hash="hash_1",
            ),
            SafetyCrisisEvent(
                event_id="evt_2",
                message_id="msg_2",
                session_id="sess_2",
                student_id_hash="hash_2",
            ),
        ]
        
        result = publisher.publish_batch(events)
        
        assert result == 2
        mock_kinesis.put_records.assert_called_once()
    
    def test_publish_batch_empty_returns_zero(self):
        """Empty batch should return 0."""
        publisher = CrisisEventPublisher(enabled=True)
        
        result = publisher.publish_batch([])
        
        assert result == 0
