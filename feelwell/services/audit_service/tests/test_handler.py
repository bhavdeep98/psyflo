"""Tests for Audit Service HTTP handler."""
import json
import pytest
from feelwell.shared.utils import configure_pii_salt


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def client():
    from feelwell.services.audit_service.handler import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get('/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['service'] == 'audit-service'
        assert 'chain_valid' in data


class TestLogAuditEntry:
    def test_log_audit_entry(self, client):
        response = client.post(
            '/audit/log',
            json={
                'action': 'view_conversation',
                'entity_type': 'student',
                'entity_id': 'hash_abc123',
                'actor_id': 'counselor_123',
                'actor_role': 'counselor',
                'school_id': 'school_001',
                'details': {'justification': 'routine_check'},
            },
            content_type='application/json',
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'entry_id' in data
        assert data['action'] == 'view_conversation'
        assert 'entry_hash' in data
    
    def test_log_missing_fields(self, client):
        response = client.post(
            '/audit/log',
            json={'action': 'view_conversation'},
            content_type='application/json',
        )
        assert response.status_code == 400
    
    def test_log_invalid_action(self, client):
        response = client.post(
            '/audit/log',
            json={
                'action': 'invalid_action',
                'entity_type': 'student',
                'entity_id': 'hash_abc',
                'actor_id': 'user_123',
                'actor_role': 'admin',
            },
            content_type='application/json',
        )
        assert response.status_code == 400


class TestLogDataAccess:
    def test_log_data_access(self, client):
        response = client.post(
            '/audit/data-access',
            json={
                'action': 'view_conversation',
                'student_id_hash': 'hash_abc123',
                'accessor_id': 'counselor_123',
                'accessor_role': 'counselor',
                'school_id': 'school_001',
                'justification': 'routine_check',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'entry_id' in data
        assert data['action'] == 'view_conversation'
    
    def test_data_access_missing_fields(self, client):
        response = client.post(
            '/audit/data-access',
            json={'action': 'view_conversation'},
            content_type='application/json',
        )
        assert response.status_code == 400


class TestLogCrisisEvent:
    def test_log_crisis_detected(self, client):
        response = client.post(
            '/audit/crisis',
            json={
                'action': 'crisis_detected',
                'crisis_id': 'crisis_abc123',
                'student_id_hash': 'hash_abc123',
                'actor_id': 'system',
                'actor_role': 'system',
                'school_id': 'school_001',
                'details': {'trigger_source': 'safety_service'},
            },
            content_type='application/json',
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert data['action'] == 'crisis_detected'
    
    def test_log_crisis_acknowledged(self, client):
        response = client.post(
            '/audit/crisis',
            json={
                'action': 'crisis_acknowledged',
                'crisis_id': 'crisis_abc123',
                'student_id_hash': 'hash_abc123',
                'actor_id': 'counselor_123',
                'actor_role': 'counselor',
            },
            content_type='application/json',
        )
        
        assert response.status_code == 201


class TestQueryAuditEntries:
    def test_query_all_entries(self, client):
        # First create some entries
        client.post(
            '/audit/log',
            json={
                'action': 'view_conversation',
                'entity_type': 'student',
                'entity_id': 'hash_query_test',
                'actor_id': 'counselor_123',
                'actor_role': 'counselor',
            },
            content_type='application/json',
        )
        
        response = client.get('/audit/query')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'count' in data
        assert 'entries' in data
    
    def test_query_by_entity_type(self, client):
        response = client.get('/audit/query?entity_type=student')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        for entry in data['entries']:
            assert entry['entity_type'] == 'student'
    
    def test_query_invalid_entity_type(self, client):
        response = client.get('/audit/query?entity_type=invalid')
        assert response.status_code == 400


class TestVerifyChain:
    def test_verify_chain_valid(self, client):
        response = client.get('/audit/verify')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['chain_valid'] is True
