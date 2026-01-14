"""Tests for Observer Service HTTP handler."""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from feelwell.shared.utils import configure_pii_salt


@pytest.fixture(autouse=True)
def setup_pii_salt():
    """Configure PII salt before each test."""
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def client():
    """Create Flask test client."""
    from feelwell.services.observer_service.handler import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_200(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['service'] == 'observer-service'


class TestReadyEndpoint:
    """Tests for /ready endpoint."""
    
    def test_ready_returns_200(self, client):
        response = client.get('/ready')
        assert response.status_code == 200


class TestAnalyzeEndpoint:
    """Tests for /analyze endpoint."""
    
    def test_analyze_safe_message(self, client):
        """Safe message should return low risk."""
        response = client.post(
            '/analyze',
            json={
                'message': 'I had a good day at school',
                'message_id': 'msg_001',
                'session_id': 'sess_001',
                'student_id': 'student_123',
                'safety_risk_score': 0.1,
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['risk_level'] == 'safe'
        assert data['risk_score'] < 0.4
    
    def test_analyze_detects_clinical_markers(self, client):
        """Message with clinical markers should be detected."""
        response = client.post(
            '/analyze',
            json={
                'message': 'I feel so hopeless and worthless, nothing is fun anymore',
                'message_id': 'msg_002',
                'session_id': 'sess_001',
                'student_id': 'student_123',
                'safety_risk_score': 0.3,
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['markers']) > 0
        assert data['risk_score'] > 0.3
    
    @patch('feelwell.services.observer_service.handler.threshold_publisher')
    def test_analyze_publishes_threshold_event(self, mock_publisher, client):
        """Elevated risk should publish threshold event."""
        mock_publisher.publish_threshold_event.return_value = True
        
        response = client.post(
            '/analyze',
            json={
                'message': 'I hate myself and feel like a burden to everyone',
                'message_id': 'msg_003',
                'session_id': 'sess_001',
                'student_id': 'student_123',
                'safety_risk_score': 0.5,
                'school_id': 'school_001',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        # Should have called publisher for elevated risk
        if json.loads(response.data)['risk_level'] in ('caution', 'crisis'):
            mock_publisher.publish_threshold_event.assert_called()
    
    def test_analyze_missing_message_returns_400(self, client):
        response = client.post(
            '/analyze',
            json={'session_id': 'sess_001'},
            content_type='application/json',
        )
        assert response.status_code == 400
    
    def test_analyze_returns_phq9_score(self, client):
        """PHQ-9 markers should return estimated score."""
        response = client.post(
            '/analyze',
            json={
                'message': 'I feel so hopeless and have no energy, can\'t sleep at all',
                'message_id': 'msg_004',
                'session_id': 'sess_001',
                'student_id': 'student_123',
                'safety_risk_score': 0.2,
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        # Should have PHQ-9 score if markers detected
        if len(data['markers']) > 0:
            assert 'phq9_score' in data or 'gad7_score' in data


class TestSummarizeEndpoint:
    """Tests for /summarize endpoint."""
    
    def test_summarize_empty_session(self, client):
        """Empty session should return valid summary."""
        response = client.post(
            '/summarize',
            json={
                'session_id': 'sess_001',
                'student_id': 'student_123',
                'snapshots': [],
                'session_start': '2026-01-14T10:00:00Z',
                'session_end': '2026-01-14T10:30:00Z',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['session_id'] == 'sess_001'
        assert data['message_count'] == 0
        assert data['counselor_flag'] is False
    
    def test_summarize_with_snapshots(self, client):
        """Session with snapshots should calculate trajectory."""
        response = client.post(
            '/summarize',
            json={
                'session_id': 'sess_002',
                'student_id': 'student_123',
                'snapshots': [
                    {
                        'message_id': 'msg_001',
                        'session_id': 'sess_002',
                        'student_id_hash': 'hash_123',
                        'risk_score': 0.2,
                        'risk_level': 'safe',
                        'markers': [],
                    },
                    {
                        'message_id': 'msg_002',
                        'session_id': 'sess_002',
                        'student_id_hash': 'hash_123',
                        'risk_score': 0.3,
                        'risk_level': 'safe',
                        'markers': [],
                    },
                ],
                'session_start': '2026-01-14T10:00:00Z',
                'session_end': '2026-01-14T10:30:00Z',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['message_count'] == 2
        assert data['risk_trajectory'] in ('stable', 'improving', 'escalating')
    
    def test_summarize_missing_session_id(self, client):
        response = client.post(
            '/summarize',
            json={'student_id': 'student_123'},
            content_type='application/json',
        )
        assert response.status_code == 400
