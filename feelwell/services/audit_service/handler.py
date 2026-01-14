"""Audit Service HTTP handler - Immutable audit trail endpoints.

Per ADR-005: All data access operations must emit audit events.
Provides HTTP interface for audit logging and querying.
"""
import logging
import os
from datetime import datetime
from flask import Flask, request, jsonify
from typing import Optional

from feelwell.shared.utils import configure_pii_salt
from .audit_logger import AuditLogger, AuditAction, AuditEntity

logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Configure PII salt
pii_salt = os.getenv("PII_HASH_SALT", "default_dev_salt_change_in_production_32chars")
configure_pii_salt(pii_salt)

# Initialize audit logger
audit_logger = AuditLogger()


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "audit-service",
        "chain_valid": audit_logger.verify_chain(),
    }), 200


@app.route("/ready", methods=["GET"])
def ready():
    """Readiness check."""
    if audit_logger is None:
        return jsonify({"status": "not_ready"}), 503
    return jsonify({"status": "ready"}), 200


@app.route("/audit/log", methods=["POST"])
def log_audit_entry():
    """Log a new audit entry.
    
    Request Body:
        {
            "action": "view_conversation",
            "entity_type": "student",
            "entity_id": "hash_abc123",
            "actor_id": "counselor_123",
            "actor_role": "counselor",
            "school_id": "school_001",
            "details": {"justification": "routine_check"}
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        # Validate required fields
        action_str = data.get("action")
        entity_type_str = data.get("entity_type")
        entity_id = data.get("entity_id")
        actor_id = data.get("actor_id")
        actor_role = data.get("actor_role")
        
        if not all([action_str, entity_type_str, entity_id, actor_id, actor_role]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Parse enums
        try:
            action = AuditAction(action_str)
            entity_type = AuditEntity(entity_type_str)
        except ValueError as e:
            return jsonify({"error": f"Invalid enum value: {str(e)}"}), 400
        
        entry = audit_logger.log(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            actor_role=actor_role,
            school_id=data.get("school_id"),
            details=data.get("details"),
        )
        
        return jsonify({
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action.value,
            "entity_type": entry.entity_type.value,
            "entry_hash": entry.entry_hash[:16] + "...",
        }), 201
        
    except Exception as e:
        logger.error("AUDIT_LOG_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to log audit entry"}), 500


@app.route("/audit/data-access", methods=["POST"])
def log_data_access():
    """Log data access event (FERPA compliance).
    
    Request Body:
        {
            "action": "view_conversation",
            "student_id_hash": "hash_abc123",
            "accessor_id": "counselor_123",
            "accessor_role": "counselor",
            "school_id": "school_001",
            "justification": "routine_check"
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        action_str = data.get("action")
        student_id_hash = data.get("student_id_hash")
        accessor_id = data.get("accessor_id")
        accessor_role = data.get("accessor_role")
        
        if not all([action_str, student_id_hash, accessor_id, accessor_role]):
            return jsonify({"error": "Missing required fields"}), 400
        
        try:
            action = AuditAction(action_str)
        except ValueError:
            return jsonify({"error": f"Invalid action: {action_str}"}), 400
        
        entry = audit_logger.log_data_access(
            action=action,
            student_id_hash=student_id_hash,
            accessor_id=accessor_id,
            accessor_role=accessor_role,
            school_id=data.get("school_id"),
            justification=data.get("justification"),
        )
        
        return jsonify({
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action.value,
        }), 201
        
    except Exception as e:
        logger.error("AUDIT_DATA_ACCESS_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to log data access"}), 500


@app.route("/audit/crisis", methods=["POST"])
def log_crisis_event():
    """Log crisis-related audit entry.
    
    Request Body:
        {
            "action": "crisis_detected",
            "crisis_id": "crisis_abc123",
            "student_id_hash": "hash_abc123",
            "actor_id": "system",
            "actor_role": "system",
            "school_id": "school_001",
            "details": {"trigger_source": "safety_service"}
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        action_str = data.get("action")
        crisis_id = data.get("crisis_id")
        student_id_hash = data.get("student_id_hash")
        actor_id = data.get("actor_id")
        actor_role = data.get("actor_role")
        
        if not all([action_str, crisis_id, student_id_hash, actor_id, actor_role]):
            return jsonify({"error": "Missing required fields"}), 400
        
        try:
            action = AuditAction(action_str)
        except ValueError:
            return jsonify({"error": f"Invalid action: {action_str}"}), 400
        
        entry = audit_logger.log_crisis_event(
            action=action,
            crisis_id=crisis_id,
            student_id_hash=student_id_hash,
            actor_id=actor_id,
            actor_role=actor_role,
            school_id=data.get("school_id"),
            details=data.get("details"),
        )
        
        return jsonify({
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action.value,
        }), 201
        
    except Exception as e:
        logger.error("AUDIT_CRISIS_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to log crisis event"}), 500


@app.route("/audit/query", methods=["GET"])
def query_audit_entries():
    """Query audit entries.
    
    Query Params:
        entity_type: Filter by entity type
        entity_id: Filter by entity ID
        action: Filter by action
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
    """
    try:
        entity_type = None
        entity_type_str = request.args.get("entity_type")
        if entity_type_str:
            try:
                entity_type = AuditEntity(entity_type_str)
            except ValueError:
                return jsonify({"error": f"Invalid entity_type: {entity_type_str}"}), 400
        
        action = None
        action_str = request.args.get("action")
        if action_str:
            try:
                action = AuditAction(action_str)
            except ValueError:
                return jsonify({"error": f"Invalid action: {action_str}"}), 400
        
        start_date = None
        start_str = request.args.get("start_date")
        if start_str:
            start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        
        end_date = None
        end_str = request.args.get("end_date")
        if end_str:
            end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        
        entries = audit_logger.query(
            entity_type=entity_type,
            entity_id=request.args.get("entity_id"),
            action=action,
            start_date=start_date,
            end_date=end_date,
        )
        
        return jsonify({
            "count": len(entries),
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "timestamp": e.timestamp.isoformat(),
                    "action": e.action.value,
                    "entity_type": e.entity_type.value,
                    "entity_id": e.entity_id,
                    "actor_id": e.actor_id,
                    "actor_role": e.actor_role,
                    "school_id": e.school_id,
                }
                for e in entries
            ],
        }), 200
        
    except Exception as e:
        logger.error("AUDIT_QUERY_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to query audit entries"}), 500


@app.route("/audit/verify", methods=["GET"])
def verify_chain():
    """Verify integrity of audit chain."""
    try:
        is_valid = audit_logger.verify_chain()
        
        return jsonify({
            "chain_valid": is_valid,
            "message": "Audit chain integrity verified" if is_valid else "CHAIN INTEGRITY COMPROMISED",
        }), 200 if is_valid else 500
        
    except Exception as e:
        logger.error("AUDIT_VERIFY_ERROR", extra={"error": str(e)})
        return jsonify({"error": "Failed to verify chain"}), 500


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    port = int(os.getenv("PORT", "8004"))
    app.run(host="0.0.0.0", port=port, debug=False)
