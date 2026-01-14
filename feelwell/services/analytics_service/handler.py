"""Analytics Service HTTP Handler - Counselor Dashboard API.

Provides endpoints for counselor dashboard with k-anonymity enforcement.
Per ADR-006: All aggregations suppress data if group size k < 5.

Endpoints:
- GET /health - Health check
- GET /ready - Readiness check
- GET /flagged-sessions - Get sessions flagged for counselor review
- GET /mood-trends - Aggregate mood trends by time period
- GET /school-overview - School-level risk overview
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from flask import Flask, request, jsonify

from feelwell.shared.utils import hash_pii
from .k_anonymity import KAnonymityEnforcer, AggregateResult

logger = logging.getLogger(__name__)

app = Flask(__name__)


@dataclass(frozen=True)
class FlaggedSession:
    """Session flagged for counselor review."""
    session_id: str
    student_id_hash: str
    school_id: str
    end_risk_score: float
    risk_trajectory: str
    phq9_score: Optional[int]
    gad7_score: Optional[int]
    counselor_flag_reason: str
    session_end: datetime
    message_count: int


@dataclass
class AnalyticsConfig:
    """Configuration for analytics service."""
    k_anonymity_threshold: int = 5
    default_lookback_days: int = 7
    max_lookback_days: int = 90


class AnalyticsHandler:
    """Handler for analytics/dashboard endpoints."""
    
    def __init__(
        self,
        config: Optional[AnalyticsConfig] = None,
        k_enforcer: Optional[KAnonymityEnforcer] = None,
    ):
        """Initialize handler with dependencies.
        
        Args:
            config: Analytics configuration
            k_enforcer: K-anonymity enforcer (injected for testing)
        """
        self.config = config or AnalyticsConfig()
        self.k_enforcer = k_enforcer or KAnonymityEnforcer(
            k_threshold=self.config.k_anonymity_threshold
        )
        
        # In-memory storage for prototype (replace with DB in production)
        self._flagged_sessions: List[FlaggedSession] = []
        self._session_summaries: List[Dict[str, Any]] = []
        
        logger.info(
            "ANALYTICS_HANDLER_INITIALIZED",
            extra={
                "k_threshold": self.config.k_anonymity_threshold,
                "default_lookback_days": self.config.default_lookback_days,
            }
        )
    
    def add_flagged_session(self, session: FlaggedSession) -> None:
        """Add a flagged session (called by Observer Service).
        
        Args:
            session: FlaggedSession to add
        """
        self._flagged_sessions.append(session)
        logger.info(
            "FLAGGED_SESSION_ADDED",
            extra={
                "session_id": session.session_id,
                "student_id_hash": session.student_id_hash,
                "school_id": session.school_id,
                "risk_score": session.end_risk_score,
            }
        )
    
    def add_session_summary(self, summary: Dict[str, Any]) -> None:
        """Add a session summary for trend analysis.
        
        Args:
            summary: Session summary dictionary
        """
        self._session_summaries.append(summary)
    
    def get_flagged_sessions(
        self,
        school_id: str,
        days: int = 7,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """Get flagged sessions for a school.
        
        Args:
            school_id: School identifier
            days: Lookback period in days
            limit: Maximum sessions to return
            
        Returns:
            Dictionary with flagged sessions and metadata
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Filter sessions for school and time period
        filtered = [
            s for s in self._flagged_sessions
            if s.school_id == school_id and s.session_end >= cutoff
        ]
        
        # Sort by risk score descending
        filtered.sort(key=lambda s: s.end_risk_score, reverse=True)
        
        # Apply limit
        limited = filtered[:limit]
        
        logger.info(
            "FLAGGED_SESSIONS_RETRIEVED",
            extra={
                "school_id": school_id,
                "days": days,
                "total_found": len(filtered),
                "returned": len(limited),
            }
        )
        
        return {
            "school_id": school_id,
            "period_days": days,
            "total_flagged": len(filtered),
            "sessions": [
                {
                    "session_id": s.session_id,
                    "student_id_hash": s.student_id_hash,
                    "end_risk_score": s.end_risk_score,
                    "risk_trajectory": s.risk_trajectory,
                    "phq9_score": s.phq9_score,
                    "gad7_score": s.gad7_score,
                    "flag_reason": s.counselor_flag_reason,
                    "session_end": s.session_end.isoformat() + "Z",
                    "message_count": s.message_count,
                }
                for s in limited
            ],
        }
    
    def get_mood_trends(
        self,
        school_id: str,
        group_by: str = "grade_level",
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get aggregate mood trends with k-anonymity.
        
        Args:
            school_id: School identifier
            group_by: Field to group by (grade_level, etc.)
            days: Lookback period
            
        Returns:
            Dictionary with trends (suppressed if k < 5)
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Filter summaries for school and time period
        filtered = [
            s for s in self._session_summaries
            if s.get("school_id") == school_id
            and s.get("timestamp", datetime.min) >= cutoff
        ]
        
        # Aggregate with k-anonymity
        results = self.k_enforcer.aggregate_with_anonymity(
            records=filtered,
            group_by=group_by,
            aggregate_field="end_risk_score",
            aggregation="avg",
        )
        
        # Format response
        trends = {}
        for key, result in results.items():
            if result.suppressed:
                trends[key] = {
                    "suppressed": True,
                    "reason": result.suppression_reason,
                    "group_size": result.group_size,
                }
            else:
                trends[key] = {
                    "suppressed": False,
                    "avg_risk_score": round(result.data, 3) if result.data else 0,
                    "group_size": result.group_size,
                }
        
        logger.info(
            "MOOD_TRENDS_RETRIEVED",
            extra={
                "school_id": school_id,
                "group_by": group_by,
                "days": days,
                "groups_returned": len(trends),
            }
        )
        
        return {
            "school_id": school_id,
            "period_days": days,
            "group_by": group_by,
            "k_anonymity_threshold": self.config.k_anonymity_threshold,
            "trends": trends,
        }
    
    def get_school_overview(self, school_id: str, days: int = 7) -> Dict[str, Any]:
        """Get school-level risk overview with k-anonymity.
        
        Args:
            school_id: School identifier
            days: Lookback period
            
        Returns:
            Dictionary with school overview (suppressed if k < 5)
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        # Filter summaries for school
        filtered = [
            s for s in self._session_summaries
            if s.get("school_id") == school_id
            and s.get("timestamp", datetime.min) >= cutoff
        ]
        
        # Count unique students
        unique_students = set(s.get("student_id_hash") for s in filtered)
        student_count = len(unique_students)
        
        # Check k-anonymity for school-level stats
        result = self.k_enforcer.check_and_suppress(
            data={
                "total_sessions": len(filtered),
                "unique_students": student_count,
                "flagged_sessions": sum(
                    1 for s in filtered if s.get("counselor_flag", False)
                ),
            },
            group_size=student_count,
            context=f"school_overview:{school_id}",
        )
        
        if result.suppressed:
            logger.warning(
                "SCHOOL_OVERVIEW_SUPPRESSED",
                extra={
                    "school_id": school_id,
                    "student_count": student_count,
                    "reason": result.suppression_reason,
                }
            )
            return {
                "school_id": school_id,
                "period_days": days,
                "suppressed": True,
                "reason": result.suppression_reason,
            }
        
        # Calculate risk distribution
        risk_scores = [s.get("end_risk_score", 0) for s in filtered]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        
        high_risk_count = sum(1 for r in risk_scores if r >= 0.7)
        medium_risk_count = sum(1 for r in risk_scores if 0.4 <= r < 0.7)
        low_risk_count = sum(1 for r in risk_scores if r < 0.4)
        
        logger.info(
            "SCHOOL_OVERVIEW_RETRIEVED",
            extra={
                "school_id": school_id,
                "days": days,
                "student_count": student_count,
                "session_count": len(filtered),
            }
        )
        
        return {
            "school_id": school_id,
            "period_days": days,
            "suppressed": False,
            "overview": {
                "total_sessions": len(filtered),
                "unique_students": student_count,
                "flagged_sessions": result.data["flagged_sessions"],
                "avg_risk_score": round(avg_risk, 3),
                "risk_distribution": {
                    "high": high_risk_count,
                    "medium": medium_risk_count,
                    "low": low_risk_count,
                },
            },
        }


# Global handler instance
_handler: Optional[AnalyticsHandler] = None


def get_handler() -> AnalyticsHandler:
    """Get or create the global handler instance."""
    global _handler
    if _handler is None:
        _handler = AnalyticsHandler()
    return _handler


def set_handler(handler: AnalyticsHandler) -> None:
    """Set the global handler (for testing)."""
    global _handler
    _handler = handler


# Flask routes
@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "analytics-service"})


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness check endpoint."""
    return jsonify({"status": "ready", "service": "analytics-service"})


@app.route("/flagged-sessions", methods=["GET"])
def flagged_sessions():
    """Get flagged sessions for counselor review.
    
    Query params:
        school_id: Required - School identifier
        days: Optional - Lookback period (default 7)
        limit: Optional - Max sessions (default 50)
    """
    school_id = request.args.get("school_id")
    if not school_id:
        return jsonify({"error": "school_id is required"}), 400
    
    days = int(request.args.get("days", 7))
    limit = int(request.args.get("limit", 50))
    
    handler = get_handler()
    result = handler.get_flagged_sessions(school_id, days, limit)
    
    return jsonify(result)


@app.route("/mood-trends", methods=["GET"])
def mood_trends():
    """Get aggregate mood trends with k-anonymity.
    
    Query params:
        school_id: Required - School identifier
        group_by: Optional - Grouping field (default grade_level)
        days: Optional - Lookback period (default 7)
    """
    school_id = request.args.get("school_id")
    if not school_id:
        return jsonify({"error": "school_id is required"}), 400
    
    group_by = request.args.get("group_by", "grade_level")
    days = int(request.args.get("days", 7))
    
    handler = get_handler()
    result = handler.get_mood_trends(school_id, group_by, days)
    
    return jsonify(result)


@app.route("/school-overview", methods=["GET"])
def school_overview():
    """Get school-level risk overview.
    
    Query params:
        school_id: Required - School identifier
        days: Optional - Lookback period (default 7)
    """
    school_id = request.args.get("school_id")
    if not school_id:
        return jsonify({"error": "school_id is required"}), 400
    
    days = int(request.args.get("days", 7))
    
    handler = get_handler()
    result = handler.get_school_overview(school_id, days)
    
    return jsonify(result)


@app.route("/sessions", methods=["POST"])
def add_session():
    """Add a session summary (called by Observer Service).
    
    Body:
        session_id: Session identifier
        student_id_hash: Hashed student ID
        school_id: School identifier
        end_risk_score: Final risk score
        counselor_flag: Whether flagged for review
        ... other summary fields
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body required"}), 400
    
    required = ["session_id", "student_id_hash", "school_id"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400
    
    # Add timestamp if not present
    if "timestamp" not in data:
        data["timestamp"] = datetime.utcnow()
    
    handler = get_handler()
    handler.add_session_summary(data)
    
    # If flagged, also add to flagged sessions
    if data.get("counselor_flag", False):
        flagged = FlaggedSession(
            session_id=data["session_id"],
            student_id_hash=data["student_id_hash"],
            school_id=data["school_id"],
            end_risk_score=data.get("end_risk_score", 0.0),
            risk_trajectory=data.get("risk_trajectory", "stable"),
            phq9_score=data.get("phq9_score"),
            gad7_score=data.get("gad7_score"),
            counselor_flag_reason=data.get("flag_reason", "elevated_risk"),
            session_end=data.get("timestamp", datetime.utcnow()),
            message_count=data.get("message_count", 0),
        )
        handler.add_flagged_session(flagged)
    
    return jsonify({"status": "accepted", "session_id": data["session_id"]}), 201


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
