"""Tests for Crisis Engine HTTP handler."""
import json
import pytest
from unittest.mock import patch, MagicMock

from feelwell.shared.utils import configure_pii_salt


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def client():
    from feelwell.services.crisis_engine.http_handler import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['service'] == 'crisis-engine'


class TestSafetyCrisisEndpoint:
    def test_handle_safety_crisis(self, client):
        response = client.post(
            '/crisis/safety',
            json={
                'student_id_hash': 'hash_abc123',
                'session_id': 'sess_001',
                'matched_keywords': ['kill myself'],
                'school_id': 'school_001',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'crisis_id' in data
        assert data['state'] == 'notifying'
        assert data['escalation_path'] == 'counselor_alert'
    
    def test_safety_crisis_missing_fields(self, client):
        response = client.post(
            '/crisis/safety',
            json={'school_id': 'school_001'},
            content_type='application/json',
        )
        assert response.status_code == 400


class TestObserverThresholdEndpoint:
    def test_handle_observer_threshold(self, client):
        response = client.post(
            '/crisis/observer',
            json={
                'student_id_hash': 'hash_abc123',
                'session_id': 'sess_001',
                'risk_score': 0.85,
                'phq9_score': 15,
                'school_id': 'school_001',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'crisis_id' in data
        assert data['escalation_path'] == 'counselor_alert'


class TestCrisisLifecycle:
    def test_acknowledge_crisis(self, client):
        # First create a crisis
        create_response = client.post(
            '/crisis/safety',
            json={
                'student_id_hash': 'hash_abc123',
                'session_id': 'sess_002',
                'matched_keywords': ['suicide'],
                'school_id': 'school_001',
            },
            content_type='application/json',
        )
        crisis_id = json.loads(create_response.data)['crisis_id']
        
        # Acknowledge it
        ack_response = client.post(
            f'/crisis/{crisis_id}/acknowledge',
            json={'acknowledged_by': 'counselor_123'},
            content_type='application/json',
        )
        
        assert ack_response.status_code == 200
        data = json.loads(ack_response.data)
        assert data['state'] == 'acknowledged'
        assert data['acknowledged_by'] == 'counselor_123'
    
    def test_resolve_crisis(self, client):
        # Create and acknowledge
        create_response = client.post(
            '/crisis/safety',
            json={
                'student_id_hash': 'hash_abc123',
                'session_id': 'sess_003',
                'matched_keywords': ['hurt myself'],
            },
            content_type='application/json',
        )
        crisis_id = json.loads(create_response.data)['crisis_id']
        
        client.post(
            f'/crisis/{crisis_id}/acknowledge',
            json={'acknowledged_by': 'counselor_123'},
            content_type='application/json',
        )
        
        # Resolve
        resolve_response = client.post(
            f'/crisis/{crisis_id}/resolve',
            json={
                'resolved_by': 'counselor_123',
                'resolution_notes': 'Student connected with support',
            },
            content_type='application/json',
        )
        
        assert resolve_response.status_code == 200
        data = json.loads(resolve_response.data)
        assert data['state'] == 'resolved'
    
    def test_acknowledge_nonexistent_crisis(self, client):
        response = client.post(
            '/crisis/nonexistent_id/acknowledge',
            json={'acknowledged_by': 'counselor_123'},
            content_type='application/json',
        )
        assert response.status_code == 404


class TestActiveCrises:
    def test_get_active_crises(self, client):
        # Create a crisis
        client.post(
            '/crisis/safety',
            json={
                'student_id_hash': 'hash_abc123',
                'session_id': 'sess_004',
                'matched_keywords': ['suicide'],
                'school_id': 'school_001',
            },
            content_type='application/json',
        )
        
        # Get active crises
        response = client.get('/crisis/active')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'count' in data
        assert 'crises' in data
        assert data['count'] >= 1
    
    def test_filter_by_school(self, client):
        # Create crisis for specific school
        client.post(
            '/crisis/safety',
            json={
                'student_id_hash': 'hash_xyz',
                'session_id': 'sess_005',
                'matched_keywords': ['hurt myself'],
                'school_id': 'school_002',
            },
            content_type='application/json',
        )
        
        # Filter by school
        response = client.get('/crisis/active?school_id=school_002')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        # All returned crises should be from school_002
        for crisis in data['crises']:
            if crisis.get('school_id'):
                assert crisis['school_id'] == 'school_002' or crisis.get('school_id') is None
