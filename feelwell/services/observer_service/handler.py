"""Observer Service HTTP handler - Clinical analysis endpoint.

This module provides the HTTP interface for the Observer Service.
Analyzes messages asynchronously after Safety Service clears them.

Per ADR-003: No PII in logs - use hash_pii() for student identifiers.
Per ADR-004: Publishes threshold events to Kinesis when risk elevated.
"""
import logging
import os
from flask import Flask, request, jsonify
from typing import Optional

from feelwell.shared.utils import hash_pii, configure_pii_salt
from feelwell.shared.models import RiskLevel
from .analyzer import MessageAnalyzer, AnalysisConfig
from .session_summarizer import SessionSummarizer
from .clinical_markers import ClinicalMarkerDetector
from .threshold_publisher import ThresholdEventPublisher

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure PII salt from environment
pii_salt = os.getenv("PII_HASH_SALT", "default_dev_salt_change_in_production_32chars")
configure_pii_salt(pii_salt)

# Initialize components
config = AnalysisConfig(
    caution_threshold=float(os.getenv("CAUTION_THRESHOLD", "0.4")),
    crisis_threshold=float(os.getenv("CRISIS_THRESHOLD", "0.7")),
)
marker_detector = ClinicalMarkerDetector()
analyzer = MessageAnalyzer(config=config, marker_detector=marker_detector)
summarizer = SessionSummarizer(marker_detector=marker_detector)

# Initialize threshold publisher
threshold_publisher = ThresholdEventPublisher(
    stream_name=os.getenv("KINESIS_STREAM_NAME", "feelwell-crisis-events"),
    enabled=os.getenv("THRESHOLD_PUBLISHING_ENABLED", "true").lower() == "true",
)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for ECS/ALB."""
    return jsonify({
        "status": "healthy",
        "service": "observer-service",
    }), 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness check - verifies analyzer is initialized."""
    if analyzer is None:
        return jsonify({"status": "not_ready", "reason": "analyzer_not_initialized"}), 503
    return jsonify({"status": "ready"}), 200


@app.route("/analyze", methods=["POST"])
def analyze_message():
    """Analyze a message for clinical markers and risk.
    
    Called asynchronously after Safety Service clears the message.
    Does NOT block the chat flow.
    
    Request Body:
        {
            "message": "Student message text",
            "message_id": "msg_123",
            "session_id": "sess_456",
            "student_id": "student_789",
            "safety_risk_score": 0.3,
            "school_id": "school_001" (optional)
        }
    
    Response:
        {
            "message_id": "msg_123",
            "risk_level": "safe" | "caution" | "crisis",
            "risk_score": 0.0-1.0,
            "markers": [...],
            "phq9_score": 5 (optional),
            "gad7_score": 3 (optional)
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("ANALYZE_REQUEST_INVALID", extra={"reason": "empty_body"})
            return jsonify({"error": "Request body required"}), 400
        
        message = data.get("message")
        if not message:
            logger.warning("ANALYZE_REQUEST_INVALID", extra={"reason": "missing_message"})
            return jsonify({"error": "Missing required field: message"}), 400
        
        message_id = data.get("message_id", "unknown")
        session_id = data.get("session_id", "unknown")
        student_id = data.get("student_id", "unknown")
        safety_risk_score = float(data.get("safety_risk_score", 0.0))
        school_id = data.get("school_id")
        
        # Hash student ID for logging (ADR-003)
        student_id_hash = hash_pii(student_id)
        
        logger.info(
            "ANALYZE_REQUESTED",
            extra={
                "message_id": message_id,
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "safety_risk_score": safety_risk_score,
            }
        )
        
        # Run analysis
        snapshot = analyzer.analyze(
            message_id=message_id,
            session_id=session_id,
            student_id=student_id,
            text=message,
            safety_risk_score=safety_risk_score,
        )
        
        # Calculate clinical scores
        phq9_score = marker_detector.calculate_phq9_score(snapshot.markers)
        gad7_score = marker_detector.calculate_gad7_score(snapshot.markers)
        
        # If threshold exceeded, publish event (ADR-004)
        if snapshot.risk_level in (RiskLevel.CRISIS, RiskLevel.CAUTION):
            _handle_threshold_exceeded(
                snapshot=snapshot,
                session_id=session_id,
                student_id_hash=student_id_hash,
                school_id=school_id,
                phq9_score=phq9_score,
            )
        
        # Build response
        response = {
            "message_id": snapshot.message_id,
            "session_id": snapshot.session_id,
            "risk_level": snapshot.risk_level.value,
            "risk_score": snapshot.risk_score,
            "markers": [
                {
                    "framework": m.framework.value,
                    "item_id": m.item_id,
                    "confidence": m.confidence,
                }
                for m in snapshot.markers
            ],
        }
        
        if phq9_score is not None:
            response["phq9_score"] = phq9_score
        if gad7_score is not None:
            response["gad7_score"] = gad7_score
        
        return jsonify(response), 200
        
    except Exception as e:
        logger.error(
            "ANALYZE_ERROR",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            }
        )
        return jsonify({"error": "Analysis failed"}), 500


@app.route("/summarize", methods=["POST"])
def summarize_session():
    """Generate session summary when conversation ends.
    
    Called when a session is closed to aggregate all analysis.
    
    Request Body:
        {
            "session_id": "sess_456",
            "student_id": "student_789",
            "snapshots": [...],
            "session_start": "2026-01-14T10:00:00Z",
            "session_end": "2026-01-14T10:30:00Z"
        }
    
    Response:
        {
            "session_id": "sess_456",
            "duration_minutes": 30,
            "message_count": 15,
            "risk_trajectory": "stable" | "improving" | "escalating",
            "phq9_score": 8,
            "gad7_score": 5,
            "counselor_flag": true
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        session_id = data.get("session_id")
        student_id = data.get("student_id")
        
        if not session_id or not student_id:
            return jsonify({"error": "Missing session_id or student_id"}), 400
        
        student_id_hash = hash_pii(student_id)
        
        # Parse timestamps
        from datetime import datetime
        session_start = datetime.fromisoformat(data["session_start"].replace("Z", "+00:00"))
        session_end = datetime.fromisoformat(data["session_end"].replace("Z", "+00:00"))
        
        # Convert snapshot dicts to CurrentSnapshot objects
        from feelwell.shared.models import CurrentSnapshot, ClinicalMarker, ClinicalFramework
        snapshots = []
        for s in data.get("snapshots", []):
            markers = [
                ClinicalMarker(
                    framework=ClinicalFramework(m["framework"]),
                    item_id=m["item_id"],
                    confidence=m["confidence"],
                    source_text_hash=m.get("source_text_hash", ""),
                )
                for m in s.get("markers", [])
            ]
            snapshots.append(CurrentSnapshot(
                message_id=s["message_id"],
                session_id=s["session_id"],
                student_id_hash=s["student_id_hash"],
                risk_score=s["risk_score"],
                risk_level=RiskLevel(s["risk_level"]),
                markers=markers,
            ))
        
        logger.info(
            "SUMMARIZE_REQUESTED",
            extra={
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "snapshot_count": len(snapshots),
            }
        )
        
        # Generate summary
        summary = summarizer.summarize(
            session_id=session_id,
            student_id_hash=student_id_hash,
            snapshots=snapshots,
            session_start=session_start,
            session_end=session_end,
        )
        
        return jsonify({
            "session_id": summary.session_id,
            "student_id_hash": summary.student_id_hash,
            "duration_minutes": summary.duration_minutes,
            "message_count": summary.message_count,
            "start_risk_score": summary.start_risk_score,
            "end_risk_score": summary.end_risk_score,
            "risk_trajectory": summary.risk_trajectory,
            "phq9_score": summary.phq9_score,
            "gad7_score": summary.gad7_score,
            "counselor_flag": summary.counselor_flag,
            "marker_count": len(summary.markers_detected),
        }), 200
        
    except Exception as e:
        logger.error(
            "SUMMARIZE_ERROR",
            extra={"error": str(e), "error_type": type(e).__name__}
        )
        return jsonify({"error": "Summarization failed"}), 500


def _handle_threshold_exceeded(
    snapshot,
    session_id: str,
    student_id_hash: str,
    school_id: Optional[str],
    phq9_score: Optional[int],
) -> None:
    """Publish threshold exceeded event to Kinesis.
    
    Per ADR-004: Events go to Kinesis for decoupled processing.
    """
    if snapshot.risk_level == RiskLevel.CRISIS:
        logger.critical(
            "THRESHOLD_EXCEEDED_CRISIS",
            extra={
                "message_id": snapshot.message_id,
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "risk_score": snapshot.risk_score,
                "phq9_score": phq9_score,
            }
        )
    else:
        logger.warning(
            "THRESHOLD_EXCEEDED_CAUTION",
            extra={
                "message_id": snapshot.message_id,
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "risk_score": snapshot.risk_score,
            }
        )
    
    threshold_publisher.publish_threshold_event(
        message_id=snapshot.message_id,
        session_id=session_id,
        student_id_hash=student_id_hash,
        risk_level=snapshot.risk_level.value,
        risk_score=snapshot.risk_score,
        phq9_score=phq9_score,
        school_id=school_id,
    )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    port = int(os.getenv("PORT", "8002"))
    app.run(host="0.0.0.0", port=port, debug=False)
