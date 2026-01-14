"""Safety Service HTTP handler - Layer 1 defense endpoint.

This module provides the HTTP interface for the Safety Service.
Every student message MUST pass through /scan before reaching the LLM.

Per ADR-001: Safety checks run BEFORE LLM calls.
Per ADR-003: No PII in logs - use hash_pii() for student identifiers.
Per ADR-004: Crisis events publish to Kinesis, not direct service calls.
"""
import logging
import os
from dataclasses import asdict
from flask import Flask, request, jsonify
from typing import Optional

from feelwell.shared.utils import hash_pii, configure_pii_salt
from feelwell.shared.models import RiskLevel
from .scanner import SafetyScanner, ScanResult
from .config import SafetyConfig, ClinicalThresholds
from .crisis_publisher import CrisisEventPublisher

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure PII salt from environment
pii_salt = os.getenv("PII_HASH_SALT", "default_dev_salt_change_in_production_32chars")
configure_pii_salt(pii_salt)

# Initialize scanner with configuration
config = SafetyConfig(
    bert_scanner_enabled=os.getenv("BERT_SCANNER_ENABLED", "false").lower() == "true",
    pattern_version=os.getenv("PATTERN_VERSION", "2026.01.14"),
)
scanner = SafetyScanner(config=config)

# Initialize crisis event publisher
crisis_publisher = CrisisEventPublisher(
    stream_name=os.getenv("KINESIS_STREAM_NAME", "feelwell-crisis-events"),
    enabled=os.getenv("CRISIS_PUBLISHING_ENABLED", "true").lower() == "true",
)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for ECS/ALB.
    
    Returns:
        200 with service status
    """
    return jsonify({
        "status": "healthy",
        "service": "safety-service",
        "scanner_version": config.pattern_version,
    }), 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness check - verifies scanner is initialized.
    
    Returns:
        200 if ready, 503 if not
    """
    if scanner is None:
        return jsonify({"status": "not_ready", "reason": "scanner_not_initialized"}), 503
    return jsonify({"status": "ready"}), 200


@app.route("/scan", methods=["POST"])
def scan_message():
    """Scan a message for safety concerns.
    
    This is the PRIMARY SAFETY ENDPOINT. Every student message
    MUST pass through here before reaching the LLM.
    
    Request Body:
        {
            "message": "Student message text",
            "message_id": "msg_123",
            "session_id": "sess_456",
            "student_id": "student_789",
            "school_id": "school_001" (optional)
        }
    
    Response:
        {
            "risk_level": "safe" | "caution" | "crisis",
            "risk_score": 0.0-1.0,
            "bypass_llm": true | false,
            "matched_keywords": ["keyword1", ...],
            "scan_latency_ms": 3.2,
            "scanner_version": "2026.01.14",
            "crisis_ui": {...} (only if bypass_llm=true)
        }
    
    Error Handling:
        On ANY error, returns CAUTION level (safe failure mode).
        We never fail open - if scanner breaks, assume risk.
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data:
            logger.warning("SCAN_REQUEST_INVALID", extra={"reason": "empty_body"})
            return jsonify({"error": "Request body required"}), 400
        
        message = data.get("message")
        if not message:
            logger.warning("SCAN_REQUEST_INVALID", extra={"reason": "missing_message"})
            return jsonify({"error": "Missing required field: message"}), 400
        
        message_id = data.get("message_id", "unknown")
        session_id = data.get("session_id", "unknown")
        student_id = data.get("student_id", "unknown")
        school_id = data.get("school_id")
        
        # Hash student ID for logging (ADR-003)
        student_id_hash = hash_pii(student_id)
        
        logger.info(
            "SCAN_REQUESTED",
            extra={
                "message_id": message_id,
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "message_length": len(message),
            }
        )
        
        # Run safety scan
        result = scanner.scan(
            message_id=message_id,
            text=message,
            student_id=student_id,
        )
        
        # If crisis detected, publish event and return crisis UI
        if result.risk_level == RiskLevel.CRISIS:
            _handle_crisis(
                result=result,
                session_id=session_id,
                student_id_hash=student_id_hash,
                school_id=school_id,
                message_preview=message[:50],
            )
            
            return jsonify({
                "risk_level": result.risk_level.value,
                "risk_score": result.risk_score,
                "bypass_llm": result.bypass_llm,
                "matched_keywords": result.matched_keywords,
                "scan_latency_ms": result.scan_latency_ms,
                "scanner_version": result.scanner_version,
                "crisis_ui": _get_crisis_ui(),
            }), 200
        
        # Normal response for SAFE or CAUTION
        return jsonify({
            "risk_level": result.risk_level.value,
            "risk_score": result.risk_score,
            "bypass_llm": result.bypass_llm,
            "matched_keywords": result.matched_keywords,
            "scan_latency_ms": result.scan_latency_ms,
            "scanner_version": result.scanner_version,
        }), 200
        
    except Exception as e:
        # CRITICAL: On error, default to CAUTION (safe failure mode)
        logger.error(
            "SCAN_ERROR",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
                "action": "DEFAULTING_TO_CAUTION",
            }
        )
        return jsonify({
            "risk_level": "caution",
            "risk_score": 0.5,
            "bypass_llm": False,
            "matched_keywords": [],
            "error": "Scanner error - defaulting to caution",
            "scanner_version": config.pattern_version,
        }), 200  # Return 200 so chat service continues with caution


def _handle_crisis(
    result: ScanResult,
    session_id: str,
    student_id_hash: str,
    school_id: Optional[str],
    message_preview: str,
) -> None:
    """Handle crisis detection - publish event to Kinesis.
    
    Per ADR-004: Crisis events publish to Kinesis, not direct calls.
    This ensures the "fire alarm" works even if other services are down.
    
    Args:
        result: ScanResult from scanner
        session_id: Current session ID
        student_id_hash: Hashed student identifier
        school_id: School identifier for routing
        message_preview: First 50 chars of message (for context)
    """
    logger.critical(
        "CRISIS_DETECTED_PUBLISHING",
        extra={
            "message_id": result.message_id,
            "session_id": session_id,
            "student_id_hash": student_id_hash,
            "school_id": school_id,
            "matched_count": len(result.matched_keywords),
            "action": "PUBLISHING_TO_KINESIS",
        }
    )
    
    published = crisis_publisher.publish_crisis(
        message_id=result.message_id,
        session_id=session_id,
        student_id_hash=student_id_hash,
        school_id=school_id,
        matched_keywords=result.matched_keywords,
        risk_score=result.risk_score,
        scanner_version=result.scanner_version,
    )
    
    if not published:
        logger.error(
            "CRISIS_PUBLISH_FAILED",
            extra={
                "message_id": result.message_id,
                "session_id": session_id,
                "action": "MANUAL_REVIEW_REQUIRED",
            }
        )


def _get_crisis_ui() -> dict:
    """Get static crisis UI response.
    
    This is the "kill switch" UI - shown when LLM is bypassed.
    No AI-generated content, just static crisis resources.
    
    Returns:
        Crisis UI configuration for frontend
    """
    return {
        "title": "We're Here to Help",
        "message": (
            "It sounds like you're going through a really difficult time. "
            "Please reach out to someone who can help right now."
        ),
        "resources": [
            {
                "name": "School Counselor",
                "action": "NOTIFY_COUNSELOR",
                "description": "Your school counselor will be notified immediately",
                "priority": 1,
            },
            {
                "name": "988 Suicide & Crisis Lifeline",
                "phone": "988",
                "description": "24/7 crisis support - call or text",
                "priority": 2,
            },
            {
                "name": "Crisis Text Line",
                "text": "HOME to 741741",
                "description": "Text-based crisis support",
                "priority": 3,
            },
        ],
        "show_emergency": True,
        "counselor_notified": True,
    }


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Run development server
    port = int(os.getenv("PORT", "8001"))
    app.run(host="0.0.0.0", port=port, debug=False)
