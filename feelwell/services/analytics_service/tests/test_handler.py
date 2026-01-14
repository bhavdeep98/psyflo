"""Tests for Analytics Service HTTP handler.

Tests counselor dashboard endpoints with k-anonymity enforcement.
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from feelwell.shared.utils import configure_pii_salt
from feelwell.services.analytics_service.handler import (
    app,
    AnalyticsHandler,
    AnalyticsConfig,
    FlaggedSession,
    set_handler,
)
from feelwell.services.analytics_service.k_anonymity import KAnonymityEnforcer


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def client():
    """Flask test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def handler():
    """Fresh handler for each test."""
    h = AnalyticsHandler(config=AnalyticsConfig(k_anonymity_threshold=5))
    set_handler(h)
    return h


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_returns_200(self, client, handler):
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "analytics-service"


class TestReadyEndpoint:
    """Tests for /ready endpoint."""
    
    def test_ready_returns_200(self, client, handler):
        response = client.get("/ready")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ready"


class TestFlaggedSessionsEndpoint:
    """Tests for /flagged-sessions endpoint."""
    
    def test_requires_school_id(self, client, handler):
        response = client.get("/flagged-sessions")
        
        assert response.status_code == 400
        assert "school_id is required" in response.get_json()["error"]
    
    def test_returns_empty_when_no_sessions(self, client, handler):
        response = client.get("/flagged-sessions?school_id=school_001")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["school_id"] == "school_001"
        assert data["total_flagged"] == 0
        assert data["sessions"] == []
    
    def test_returns_flagged_sessions(self, client, handler):
        # Add flagged session
        session = FlaggedSession(
            session_id="sess_001",
            student_id_hash="hash_123",
            school_id="school_001",
            end_risk_score=0.75,
            risk_trajectory="escalating",
            phq9_score=12,
            gad7_score=8,
            counselor_flag_reason="elevated_risk",
            session_end=datetime.utcnow(),
            message_count=15,
        )
        handler.add_flagged_session(session)
        
        response = client.get("/flagged-sessions?school_id=school_001")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["total_flagged"] == 1
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "sess_001"
        assert data["sessions"][0]["end_risk_score"] == 0.75
    
    def test_filters_by_school(self, client, handler):
        # Add sessions for different schools
        handler.add_flagged_session(FlaggedSession(
            session_id="sess_001",
            student_id_hash="hash_1",
            school_id="school_001",
            end_risk_score=0.7,
            risk_trajectory="stable",
            phq9_score=None,
            gad7_score=None,
            counselor_flag_reason="test",
            session_end=datetime.utcnow(),
            message_count=10,
        ))
        handler.add_flagged_session(FlaggedSession(
            session_id="sess_002",
            student_id_hash="hash_2",
            school_id="school_002",
            end_risk_score=0.8,
            risk_trajectory="stable",
            phq9_score=None,
            gad7_score=None,
            counselor_flag_reason="test",
            session_end=datetime.utcnow(),
            message_count=10,
        ))
        
        response = client.get("/flagged-sessions?school_id=school_001")
        
        data = response.get_json()
        assert data["total_flagged"] == 1
        assert data["sessions"][0]["session_id"] == "sess_001"
    
    def test_sorts_by_risk_score_descending(self, client, handler):
        # Add sessions with different risk scores
        for i, score in enumerate([0.5, 0.9, 0.7]):
            handler.add_flagged_session(FlaggedSession(
                session_id=f"sess_{i}",
                student_id_hash=f"hash_{i}",
                school_id="school_001",
                end_risk_score=score,
                risk_trajectory="stable",
                phq9_score=None,
                gad7_score=None,
                counselor_flag_reason="test",
                session_end=datetime.utcnow(),
                message_count=10,
            ))
        
        response = client.get("/flagged-sessions?school_id=school_001")
        
        data = response.get_json()
        scores = [s["end_risk_score"] for s in data["sessions"]]
        assert scores == [0.9, 0.7, 0.5]


class TestMoodTrendsEndpoint:
    """Tests for /mood-trends endpoint."""
    
    def test_requires_school_id(self, client, handler):
        response = client.get("/mood-trends")
        
        assert response.status_code == 400
    
    def test_returns_empty_trends(self, client, handler):
        response = client.get("/mood-trends?school_id=school_001")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["school_id"] == "school_001"
        assert data["trends"] == {}
    
    def test_suppresses_small_groups(self, client, handler):
        # Add 3 sessions (below k=5 threshold)
        for i in range(3):
            handler.add_session_summary({
                "session_id": f"sess_{i}",
                "student_id_hash": f"hash_{i}",
                "school_id": "school_001",
                "grade_level": "9th",
                "end_risk_score": 0.5,
                "timestamp": datetime.utcnow(),
            })
        
        response = client.get("/mood-trends?school_id=school_001&group_by=grade_level")
        
        data = response.get_json()
        assert data["k_anonymity_threshold"] == 5
        assert "9th" in data["trends"]
        assert data["trends"]["9th"]["suppressed"] is True
    
    def test_returns_trends_above_threshold(self, client, handler):
        # Add 6 sessions (above k=5 threshold)
        for i in range(6):
            handler.add_session_summary({
                "session_id": f"sess_{i}",
                "student_id_hash": f"hash_{i}",
                "school_id": "school_001",
                "grade_level": "10th",
                "end_risk_score": 0.4 + (i * 0.05),
                "timestamp": datetime.utcnow(),
            })
        
        response = client.get("/mood-trends?school_id=school_001&group_by=grade_level")
        
        data = response.get_json()
        assert "10th" in data["trends"]
        assert data["trends"]["10th"]["suppressed"] is False
        assert data["trends"]["10th"]["group_size"] == 6
        assert "avg_risk_score" in data["trends"]["10th"]


class TestSchoolOverviewEndpoint:
    """Tests for /school-overview endpoint."""
    
    def test_requires_school_id(self, client, handler):
        response = client.get("/school-overview")
        
        assert response.status_code == 400
    
    def test_suppresses_when_few_students(self, client, handler):
        # Add 3 sessions from 3 students (below k=5)
        for i in range(3):
            handler.add_session_summary({
                "session_id": f"sess_{i}",
                "student_id_hash": f"hash_{i}",
                "school_id": "school_001",
                "end_risk_score": 0.5,
                "counselor_flag": False,
                "timestamp": datetime.utcnow(),
            })
        
        response = client.get("/school-overview?school_id=school_001")
        
        data = response.get_json()
        assert data["suppressed"] is True
        assert "reason" in data
    
    def test_returns_overview_above_threshold(self, client, handler):
        # Add 6 sessions from 6 students (above k=5)
        for i in range(6):
            handler.add_session_summary({
                "session_id": f"sess_{i}",
                "student_id_hash": f"hash_{i}",
                "school_id": "school_001",
                "end_risk_score": 0.3 + (i * 0.1),
                "counselor_flag": i >= 4,  # 2 flagged
                "timestamp": datetime.utcnow(),
            })
        
        response = client.get("/school-overview?school_id=school_001")
        
        data = response.get_json()
        assert data["suppressed"] is False
        assert data["overview"]["total_sessions"] == 6
        assert data["overview"]["unique_students"] == 6
        assert data["overview"]["flagged_sessions"] == 2
        assert "avg_risk_score" in data["overview"]
        assert "risk_distribution" in data["overview"]


class TestAddSessionEndpoint:
    """Tests for POST /sessions endpoint."""
    
    def test_requires_body(self, client, handler):
        response = client.post("/sessions", content_type="application/json")
        
        assert response.status_code == 400
    
    def test_requires_fields(self, client, handler):
        response = client.post(
            "/sessions",
            json={"session_id": "sess_001"},
            content_type="application/json",
        )
        
        assert response.status_code == 400
        assert "Missing fields" in response.get_json()["error"]
    
    def test_adds_session_summary(self, client, handler):
        response = client.post(
            "/sessions",
            json={
                "session_id": "sess_001",
                "student_id_hash": "hash_123",
                "school_id": "school_001",
                "end_risk_score": 0.5,
                "counselor_flag": False,
            },
            content_type="application/json",
        )
        
        assert response.status_code == 201
        data = response.get_json()
        assert data["status"] == "accepted"
        assert data["session_id"] == "sess_001"
    
    def test_adds_flagged_session_when_flagged(self, client, handler):
        response = client.post(
            "/sessions",
            json={
                "session_id": "sess_001",
                "student_id_hash": "hash_123",
                "school_id": "school_001",
                "end_risk_score": 0.8,
                "counselor_flag": True,
                "flag_reason": "elevated_risk",
                "risk_trajectory": "escalating",
            },
            content_type="application/json",
        )
        
        assert response.status_code == 201
        
        # Verify it appears in flagged sessions
        flagged_response = client.get("/flagged-sessions?school_id=school_001")
        flagged_data = flagged_response.get_json()
        assert flagged_data["total_flagged"] == 1


class TestKAnonymityIntegration:
    """Integration tests for k-anonymity enforcement."""
    
    def test_mixed_group_sizes(self, client, handler):
        """Test that some groups are suppressed while others aren't."""
        # Add 3 sessions for 9th grade (suppressed)
        for i in range(3):
            handler.add_session_summary({
                "session_id": f"sess_9_{i}",
                "student_id_hash": f"hash_9_{i}",
                "school_id": "school_001",
                "grade_level": "9th",
                "end_risk_score": 0.5,
                "timestamp": datetime.utcnow(),
            })
        
        # Add 7 sessions for 10th grade (not suppressed)
        for i in range(7):
            handler.add_session_summary({
                "session_id": f"sess_10_{i}",
                "student_id_hash": f"hash_10_{i}",
                "school_id": "school_001",
                "grade_level": "10th",
                "end_risk_score": 0.6,
                "timestamp": datetime.utcnow(),
            })
        
        response = client.get("/mood-trends?school_id=school_001&group_by=grade_level")
        
        data = response.get_json()
        assert data["trends"]["9th"]["suppressed"] is True
        assert data["trends"]["10th"]["suppressed"] is False
