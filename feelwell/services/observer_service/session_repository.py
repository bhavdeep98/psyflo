"""Session repository for Observer Service.

Stores session summaries in PostgreSQL for:
- Counselor dashboard queries
- Longitudinal trend analysis
- Clinical review and auditing

Per ADR-005: All data access emits audit events.
"""
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from feelwell.shared.database import (
    BaseRepository,
    ConnectionManager,
    NotFoundError,
)
from feelwell.shared.models import SessionSummary, ClinicalMarker, ClinicalFramework

logger = logging.getLogger(__name__)


class SessionRepository(BaseRepository[SessionSummary]):
    """Repository for session summaries.
    
    Stores Layer 2 analysis results for counselor review
    and longitudinal tracking.
    """
    
    def __init__(self, connection_manager: ConnectionManager):
        """Initialize session repository.
        
        Args:
            connection_manager: Database connection manager
        """
        super().__init__(connection_manager, "session_summaries")
    
    def _row_to_entity(self, row: tuple) -> SessionSummary:
        """Convert database row to SessionSummary.
        
        Expected columns:
            0: id (session_id)
            1: student_id_hash
            2: duration_minutes
            3: message_count
            4: start_risk_score
            5: end_risk_score
            6: phq9_score
            7: gad7_score
            8: risk_trajectory
            9: counselor_flag
            10: markers_json
            11: created_at
        """
        markers = []
        if row[10]:  # markers_json
            import json
            markers_data = json.loads(row[10]) if isinstance(row[10], str) else row[10]
            for m in markers_data:
                markers.append(ClinicalMarker(
                    framework=ClinicalFramework(m["framework"]),
                    item_id=m["item_id"],
                    confidence=m["confidence"],
                    source_text_hash=m.get("source_text_hash", ""),
                    detected_at=datetime.fromisoformat(m["detected_at"]) if m.get("detected_at") else datetime.utcnow(),
                ))
        
        return SessionSummary(
            session_id=row[0],
            student_id_hash=row[1],
            duration_minutes=row[2],
            message_count=row[3],
            start_risk_score=row[4],
            end_risk_score=row[5],
            phq9_score=row[6],
            gad7_score=row[7],
            risk_trajectory=row[8],
            counselor_flag=row[9],
            markers_detected=markers,
        )
    
    def _entity_to_params(self, entity: SessionSummary) -> Dict[str, Any]:
        """Convert SessionSummary to database parameters."""
        import json
        
        markers_json = json.dumps([
            {
                "framework": m.framework.value,
                "item_id": m.item_id,
                "confidence": m.confidence,
                "source_text_hash": m.source_text_hash,
                "detected_at": m.detected_at.isoformat(),
            }
            for m in entity.markers_detected
        ])
        
        return {
            "id": entity.session_id,
            "student_id_hash": entity.student_id_hash,
            "duration_minutes": entity.duration_minutes,
            "message_count": entity.message_count,
            "start_risk_score": entity.start_risk_score,
            "end_risk_score": entity.end_risk_score,
            "phq9_score": entity.phq9_score,
            "gad7_score": entity.gad7_score,
            "risk_trajectory": entity.risk_trajectory,
            "counselor_flag": entity.counselor_flag,
            "markers_json": markers_json,
            "created_at": datetime.utcnow(),
        }
    
    def find_by_student(
        self,
        student_id_hash: str,
        limit: int = 50,
    ) -> List[SessionSummary]:
        """Find sessions for a student.
        
        Args:
            student_id_hash: Hashed student identifier
            limit: Maximum sessions to return
            
        Returns:
            List of session summaries, newest first
        """
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT * FROM {self.table_name}
                    WHERE student_id_hash = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (student_id_hash, limit)
                )
                rows = cur.fetchall()
                
                return [self._row_to_entity(row) for row in rows]
    
    def find_flagged(
        self,
        school_id: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[SessionSummary]:
        """Find sessions flagged for counselor review.
        
        Args:
            school_id: Filter by school (optional)
            since: Filter by date (optional)
            limit: Maximum sessions to return
            
        Returns:
            List of flagged sessions, highest risk first
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE counselor_flag = true
        """
        params = []
        
        if since:
            query += " AND created_at >= %s"
            params.append(since)
        
        query += " ORDER BY end_risk_score DESC LIMIT %s"
        params.append(limit)
        
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
                return [self._row_to_entity(row) for row in rows]
    
    def find_by_risk_level(
        self,
        min_risk: float,
        max_risk: float = 1.0,
        since: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[SessionSummary]:
        """Find sessions within a risk score range.
        
        Args:
            min_risk: Minimum risk score
            max_risk: Maximum risk score
            since: Filter by date (optional)
            limit: Maximum sessions to return
            
        Returns:
            List of sessions in risk range
        """
        query = f"""
            SELECT * FROM {self.table_name}
            WHERE end_risk_score >= %s AND end_risk_score <= %s
        """
        params = [min_risk, max_risk]
        
        if since:
            query += " AND created_at >= %s"
            params.append(since)
        
        query += " ORDER BY end_risk_score DESC LIMIT %s"
        params.append(limit)
        
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
                return [self._row_to_entity(row) for row in rows]
    
    def get_aggregate_stats(
        self,
        since: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get aggregate statistics for sessions.
        
        Args:
            since: Filter by date (optional)
            
        Returns:
            Dictionary with aggregate stats
        """
        query = f"""
            SELECT 
                COUNT(*) as total_sessions,
                COUNT(DISTINCT student_id_hash) as unique_students,
                AVG(end_risk_score) as avg_risk_score,
                SUM(CASE WHEN counselor_flag THEN 1 ELSE 0 END) as flagged_count,
                AVG(duration_minutes) as avg_duration,
                AVG(message_count) as avg_messages
            FROM {self.table_name}
        """
        params = []
        
        if since:
            query += " WHERE created_at >= %s"
            params.append(since)
        
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                
                if row:
                    return {
                        "total_sessions": row[0] or 0,
                        "unique_students": row[1] or 0,
                        "avg_risk_score": float(row[2]) if row[2] else 0.0,
                        "flagged_count": row[3] or 0,
                        "avg_duration_minutes": float(row[4]) if row[4] else 0.0,
                        "avg_message_count": float(row[5]) if row[5] else 0.0,
                    }
                
                return {
                    "total_sessions": 0,
                    "unique_students": 0,
                    "avg_risk_score": 0.0,
                    "flagged_count": 0,
                    "avg_duration_minutes": 0.0,
                    "avg_message_count": 0.0,
                }
