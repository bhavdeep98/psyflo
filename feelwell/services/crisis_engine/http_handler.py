"""Crisis Engine HTTP handler - Crisis management endpoints.

Provides HTTP interface for crisis event management.
The main event processing happens via Kinesis consumer.

Per ADR-004: Crisis events come from Kinesis stream.
Per ADR-005: All crisis actions are audit logged.
"""
import logging
import os
from flask import Flask, request, jsonify
from typing import Optional

from feelwell.shared.utils import hash_pii, configure_pii_salt
from .handler import CrisisHandler
from .events import CrisisEventPublisher

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure PII salt
pii_salt = os.getenv("PII_HASH_SALT", "default_dev_salt_change_in_production_32chars")
configure_pii_salt(pii_salt)

# Initialize crisis handler
event_publisher = CrisisEventPublisher(
    stream_name=os.getenv("KINESIS_STREAM_NAME", "feelwell-crisis-events")
)
crisis_handler = CrisisHandler(event_publisher=event_publisher)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "crisis-engine",
    }), 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness check."""
    if crisis_handler is None:
        return jsonify({"status": "not_ready"}), 503
    return jsonify({"status": "ready"}), 200


@app.route("/crisis/safety", methods=["POST"])
def handle_safety_crisis():
    """Handle crisis detected by Safety Service.
    
    Request Body:
        {
            "student_id_hash": "hash_abc",
            "session_id": "sess_123",
            "matched_keywords": ["keyword1"],
            "school_id": "school_001"
        }
    
    Response:
        {
            "crisis_id": "crisis_abc123",
            "state": "notifying",
            "escalation_path": "counselor_alert"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        student_id_hash = data.get("student_id_hash")
        session_id = data.get("session_id")
        matched_keywords = data.get("matched_keywords", [])
        school_id = data.get("school_id")
        
        if not student_id_hash or not session_id:
            return jsonify({"error": "Missing student_id_hash or session_id"}), 400
        
        logger.critical(
            "CRISIS_SAFETY_RECEIVED",
            extra={
                "student_id_hash": student_id_hash,
                "session_id": session_id,
                "keyword_count": len(matched_keywords),
                "school_id": school_id,
            }
        )
        
        record = crisis_handler.handle_safety_crisis(
            student_id_hash=student_id_hash,
            session_id=session_id,
            matched_keywords=matched_keywords,
            school_id=school_id,
        )
        
        return jsonify({
            "crisis_id": record.crisis_id,
            "event_id": record.event_id,
            "state": record.state.value,
            "escalation_path": record.escalation_path.value,
            "created_at": record.created_at.isoformat(),
        }), 201
        
    except Exception as e:
        logger.error("CRISIS_SAFETY_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to process crisis"}), 500


@app.route("/crisis/observer", methods=["POST"])
def handle_observer_threshold():
    """Handle threshold exceeded from Observer Service.
    
    Request Body:
        {
            "student_id_hash": "hash_abc",
            "session_id": "sess_123",
            "risk_score": 0.85,
            "phq9_score": 15,
            "school_id": "school_001"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        student_id_hash = data.get("student_id_hash")
        session_id = data.get("session_id")
        risk_score = float(data.get("risk_score", 0.0))
        phq9_score = data.get("phq9_score")
        school_id = data.get("school_id")
        
        if not student_id_hash or not session_id:
            return jsonify({"error": "Missing student_id_hash or session_id"}), 400
        
        logger.critical(
            "CRISIS_OBSERVER_RECEIVED",
            extra={
                "student_id_hash": student_id_hash,
                "session_id": session_id,
                "risk_score": risk_score,
                "phq9_score": phq9_score,
            }
        )
        
        record = crisis_handler.handle_observer_threshold(
            student_id_hash=student_id_hash,
            session_id=session_id,
            risk_score=risk_score,
            phq9_score=phq9_score,
            school_id=school_id,
        )
        
        return jsonify({
            "crisis_id": record.crisis_id,
            "event_id": record.event_id,
            "state": record.state.value,
            "escalation_path": record.escalation_path.value,
        }), 201
        
    except Exception as e:
        logger.error("CRISIS_OBSERVER_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to process threshold event"}), 500


@app.route("/crisis/<crisis_id>/acknowledge", methods=["POST"])
def acknowledge_crisis(crisis_id: str):
    """Acknowledge a crisis event.
    
    Request Body:
        {
            "acknowledged_by": "counselor_123"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        acknowledged_by = data.get("acknowledged_by")
        if not acknowledged_by:
            return jsonify({"error": "Missing acknowledged_by"}), 400
        
        record = crisis_handler.acknowledge(
            crisis_id=crisis_id,
            acknowledged_by=acknowledged_by,
        )
        
        if not record:
            return jsonify({"error": "Crisis not found"}), 404
        
        logger.info(
            "CRISIS_ACKNOWLEDGED_HTTP",
            extra={
                "crisis_id": crisis_id,
                "acknowledged_by": acknowledged_by,
            }
        )
        
        return jsonify({
            "crisis_id": record.crisis_id,
            "state": record.state.value,
            "acknowledged_at": record.acknowledged_at.isoformat() if record.acknowledged_at else None,
            "acknowledged_by": record.acknowledged_by,
        }), 200
        
    except Exception as e:
        logger.error("CRISIS_ACKNOWLEDGE_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to acknowledge crisis"}), 500


@app.route("/crisis/<crisis_id>/resolve", methods=["POST"])
def resolve_crisis(crisis_id: str):
    """Resolve a crisis event.
    
    Request Body:
        {
            "resolved_by": "counselor_123",
            "resolution_notes": "Student connected with support"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        resolved_by = data.get("resolved_by")
        resolution_notes = data.get("resolution_notes", "")
        
        if not resolved_by:
            return jsonify({"error": "Missing resolved_by"}), 400
        
        record = crisis_handler.resolve(
            crisis_id=crisis_id,
            resolved_by=resolved_by,
            resolution_notes=resolution_notes,
        )
        
        if not record:
            return jsonify({"error": "Crisis not found"}), 404
        
        logger.info(
            "CRISIS_RESOLVED_HTTP",
            extra={
                "crisis_id": crisis_id,
                "resolved_by": resolved_by,
            }
        )
        
        return jsonify({
            "crisis_id": record.crisis_id,
            "state": record.state.value,
            "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
            "resolved_by": record.resolved_by,
        }), 200
        
    except Exception as e:
        logger.error("CRISIS_RESOLVE_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to resolve crisis"}), 500


@app.route("/crisis/active", methods=["GET"])
def get_active_crises():
    """Get all active (unresolved) crises.
    
    Query Params:
        school_id: Filter by school (optional)
    """
    try:
        school_id = request.args.get("school_id")
        
        active = crisis_handler.get_active_crises(school_id=school_id)
        
        return jsonify({
            "count": len(active),
            "crises": [
                {
                    "crisis_id": r.crisis_id,
                    "student_id_hash": r.student_id_hash,
                    "session_id": r.session_id,
                    "state": r.state.value,
                    "escalation_path": r.escalation_path.value,
                    "trigger_source": r.trigger_source,
                    "created_at": r.created_at.isoformat(),
                    "acknowledged_at": r.acknowledged_at.isoformat() if r.acknowledged_at else None,
                }
                for r in active
            ],
        }), 200
        
    except Exception as e:
        logger.error("CRISIS_LIST_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to list crises"}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("PORT", "8003"))
    app.run(host="0.0.0.0", port=port, debug=False)
