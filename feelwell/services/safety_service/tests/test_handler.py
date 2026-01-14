"""Tests for Safety Service HTTP handler.

Tests the /scan endpoint and crisis event publishing integration.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

from feelwell.shared.utils import configure_pii_salt


@pytest.fixture(autouse=True)
def setup_pii_salt():
    """Configure PII salt before each test."""
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def client():
    """Create Flask test client."""
    from feelwell.services.safety_service.handler import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_200(self, client):
        """Health check should return 200."""
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['service'] == 'safety-service'
    
    def test_health_includes_version(self, client):
        """Health check should include scanner version."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert 'scanner_version' in data


class TestReadyEndpoint:
    """Tests for /ready endpoint."""
    
    def test_ready_returns_200(self, client):
        """Readiness check should return 200 when scanner initialized."""
        response = client.get('/ready')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ready'


class TestScanEndpoint:
    """Tests for /scan endpoint."""
    
    def test_scan_safe_message(self, client):
        """Safe message should return SAFE risk level."""
        response = client.post(
            '/scan',
            json={
                'message': 'I had a good day at school',
                'message_id': 'msg_001',
                'session_id': 'sess_001',
                'student_id': 'student_123',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['risk_level'] == 'safe'
        assert data['bypass_llm'] is False
        assert 'crisis_ui' not in data
    
    def test_scan_caution_message(self, client):
        """Caution message should return CAUTION risk level."""
        response = client.post(
            '/scan',
            json={
                'message': 'I feel so hopeless about everything',
                'message_id': 'msg_002',
                'session_id': 'sess_001',
                'student_id': 'student_123',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['risk_level'] == 'caution'
        assert data['bypass_llm'] is False
        assert 'hopeless' in data['matched_keywords']
    
    @patch('feelwell.services.safety_service.handler.crisis_publisher')
    def test_scan_crisis_message(self, mock_publisher, client):
        """Crisis message should return CRISIS with bypass and crisis UI."""
        mock_publisher.publish_crisis.return_value = True
        
        response = client.post(
            '/scan',
            json={
                'message': 'I want to kill myself',
                'message_id': 'msg_003',
                'session_id': 'sess_001',
                'student_id': 'student_123',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['risk_level'] == 'crisis'
        assert data['bypass_llm'] is True
        assert data['risk_score'] == 1.0
        assert 'crisis_ui' in data
        assert data['crisis_ui']['show_emergency'] is True
    
    @patch('feelwell.services.safety_service.handler.crisis_publisher')
    def test_crisis_publishes_event(self, mock_publisher, client):
        """Crisis detection should publish event to Kinesis."""
        mock_publisher.publish_crisis.return_value = True
        
        client.post(
            '/scan',
            json={
                'message': 'I want to kill myself',
                'message_id': 'msg_004',
                'session_id': 'sess_002',
                'student_id': 'student_456',
                'school_id': 'school_001',
            },
            content_type='application/json',
        )
        
        mock_publisher.publish_crisis.assert_called_once()
        call_kwargs = mock_publisher.publish_crisis.call_args.kwargs
        assert call_kwargs['message_id'] == 'msg_004'
        assert call_kwargs['session_id'] == 'sess_002'
        assert call_kwargs['school_id'] == 'school_001'
    
    def test_scan_missing_message_returns_400(self, client):
        """Missing message field should return 400."""
        response = client.post(
            '/scan',
            json={'session_id': 'sess_001'},
            content_type='application/json',
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_scan_empty_body_returns_caution(self, client):
        """Empty request body triggers safe failure mode (CAUTION)."""
        response = client.post(
            '/scan',
            data='',
            content_type='application/json',
        )
        
        # Safe failure mode: return 200 with CAUTION, not 400
        # This ensures chat service continues with elevated monitoring
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['risk_level'] == 'caution'
    
    def test_scan_includes_latency(self, client):
        """Scan response should include latency measurement."""
        response = client.post(
            '/scan',
            json={
                'message': 'Hello',
                'message_id': 'msg_005',
                'session_id': 'sess_001',
                'student_id': 'student_123',
            },
            content_type='application/json',
        )
        
        data = json.loads(response.data)
        assert 'scan_latency_ms' in data
        assert data['scan_latency_ms'] >= 0


class TestErrorHandling:
    """Tests for error handling - safe failure mode."""
    
    @patch('feelwell.services.safety_service.handler.scanner')
    def test_scanner_error_returns_caution(self, mock_scanner, client):
        """Scanner error should default to CAUTION (safe failure)."""
        mock_scanner.scan.side_effect = Exception("Scanner crashed")
        
        response = client.post(
            '/scan',
            json={
                'message': 'Test message',
                'message_id': 'msg_006',
                'session_id': 'sess_001',
                'student_id': 'student_123',
            },
            content_type='application/json',
        )
        
        # Should return 200 with CAUTION, not 500
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['risk_level'] == 'caution'
        assert data['bypass_llm'] is False
        assert 'error' in data


class TestCrisisUI:
    """Tests for crisis UI response."""
    
    @patch('feelwell.services.safety_service.handler.crisis_publisher')
    def test_crisis_ui_has_resources(self, mock_publisher, client):
        """Crisis UI should include crisis resources."""
        mock_publisher.publish_crisis.return_value = True
        
        response = client.post(
            '/scan',
            json={
                'message': 'I want to end my life',
                'message_id': 'msg_007',
                'session_id': 'sess_001',
                'student_id': 'student_123',
            },
            content_type='application/json',
        )
        
        data = json.loads(response.data)
        crisis_ui = data['crisis_ui']
        
        assert 'title' in crisis_ui
        assert 'message' in crisis_ui
        assert 'resources' in crisis_ui
        assert len(crisis_ui['resources']) >= 3
        
        # Check for 988 hotline
        resource_names = [r['name'] for r in crisis_ui['resources']]
        assert '988 Suicide & Crisis Lifeline' in resource_names
