"""Audit logger - immutable audit trail per ADR-005.

All data access operations must emit audit events.
"""
import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
import uuid

logger = logging.getLogger(__name__)


class AuditAction(Enum):
    """Actions that require audit logging."""
    # Data access
    VIEW_CONVERSATION = "view_conversation"
    VIEW_STUDENT_PROFILE = "view_student_profile"
    VIEW_CLINICAL_SCORES = "view_clinical_scores"
    EXPORT_DATA = "export_data"
    
    # Data modification
    CREATE_SESSION = "create_session"
    END_SESSION = "end_session"
    UPDATE_CONSENT = "update_consent"
    DELETE_DATA = "delete_data"
    
    # Crisis events
    CRISIS_DETECTED = "crisis_detected"
    CRISIS_ACKNOWLEDGED = "crisis_acknowledged"
    CRISIS_RESOLVED = "crisis_resolved"
    
    # Administrative
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    CONFIG_CHANGED = "config_changed"


class AuditEntity(Enum):
    """Entity types for audit logging."""
    STUDENT = "student"
    COUNSELOR = "counselor"
    ADMIN = "admin"
    SESSION = "session"
    CONVERSATION = "conversation"
    CRISIS_EVENT = "crisis_event"
    SYSTEM = "system"


@dataclass(frozen=True)
class AuditEntry:
    """Immutable audit log entry.
    
    Designed for QLDB or PostgreSQL WORM storage.
    """
    entry_id: str
    timestamp: datetime
    action: AuditAction
    entity_type: AuditEntity
    entity_id: str  # Hashed if PII
    actor_id: str   # User who performed action (hashed if student)
    actor_role: str
    school_id: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)
    previous_hash: str = ""  # Chain to previous entry for verification
    entry_hash: str = ""     # Hash of this entry
    
    def compute_hash(self) -> str:
        """Compute SHA-256 hash of entry for verification.
        
        Returns:
            Hex-encoded hash string
        """
        content = {
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            "entity_type": self.entity_type.value,
            "entity_id": self.entity_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "school_id": self.school_id,
            "details": self.details,
            "previous_hash": self.previous_hash,
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()


class AuditLogger:
    """Logs audit entries to immutable storage.
    
    In production, this writes to QLDB or PostgreSQL with WORM.
    Maintains hash chain for cryptographic verification.
    """
    
    def __init__(self):
        """Initialize audit logger."""
        self._entries: list = []  # In-memory for dev; QLDB in prod
        self._last_hash: str = "genesis"
        
        logger.info("AUDIT_LOGGER_INITIALIZED")
    
    def log(
        self,
        action: AuditAction,
        entity_type: AuditEntity,
        entity_id: str,
        actor_id: str,
        actor_role: str,
        school_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log an audit entry.
        
        Args:
            action: Action being audited
            entity_type: Type of entity being acted upon
            entity_id: Identifier of entity (hashed if PII)
            actor_id: User performing action (hashed if student)
            actor_role: Role of actor (student, counselor, admin)
            school_id: School context
            details: Additional context
            
        Returns:
            Created AuditEntry
            
        Logs:
            - AUDIT_ENTRY_CREATED: After entry is stored
        """
        entry = AuditEntry(
            entry_id=f"audit_{uuid.uuid4().hex[:16]}",
            timestamp=datetime.utcnow(),
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_id=actor_id,
            actor_role=actor_role,
            school_id=school_id,
            details=details or {},
            previous_hash=self._last_hash,
        )
        
        # Compute hash (creates new instance since frozen)
        entry_hash = entry.compute_hash()
        entry = AuditEntry(
            entry_id=entry.entry_id,
            timestamp=entry.timestamp,
            action=entry.action,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            actor_id=entry.actor_id,
            actor_role=entry.actor_role,
            school_id=entry.school_id,
            details=entry.details,
            previous_hash=entry.previous_hash,
            entry_hash=entry_hash,
        )
        
        # Store entry
        self._entries.append(entry)
        self._last_hash = entry_hash
        
        logger.info(
            "AUDIT_ENTRY_CREATED",
            extra={
                "entry_id": entry.entry_id,
                "action": action.value,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "actor_role": actor_role,
                "school_id": school_id,
                "entry_hash": entry_hash[:16],  # Truncated for logs
            }
        )
        
        return entry
    
    def log_data_access(
        self,
        action: AuditAction,
        student_id_hash: str,
        accessor_id: str,
        accessor_role: str,
        school_id: Optional[str] = None,
        justification: Optional[str] = None,
    ) -> AuditEntry:
        """Convenience method for logging data access.
        
        Per FERPA: All access to student data must be logged
        with justification.
        
        Args:
            action: Access action (VIEW_*, EXPORT_*)
            student_id_hash: Hashed student identifier
            accessor_id: User accessing data
            accessor_role: Role of accessor
            school_id: School context
            justification: Reason for access (required for FERPA)
            
        Returns:
            Created AuditEntry
        """
        return self.log(
            action=action,
            entity_type=AuditEntity.STUDENT,
            entity_id=student_id_hash,
            actor_id=accessor_id,
            actor_role=accessor_role,
            school_id=school_id,
            details={"justification": justification or "routine_access"},
        )
    
    def log_crisis_event(
        self,
        action: AuditAction,
        crisis_id: str,
        student_id_hash: str,
        actor_id: str,
        actor_role: str,
        school_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log crisis-related audit entry.
        
        Args:
            action: Crisis action (DETECTED, ACKNOWLEDGED, RESOLVED)
            crisis_id: Crisis event identifier
            student_id_hash: Hashed student identifier
            actor_id: User involved
            actor_role: Role of user
            school_id: School context
            details: Additional crisis details
            
        Returns:
            Created AuditEntry
        """
        entry_details = details or {}
        entry_details["student_id_hash"] = student_id_hash
        
        return self.log(
            action=action,
            entity_type=AuditEntity.CRISIS_EVENT,
            entity_id=crisis_id,
            actor_id=actor_id,
            actor_role=actor_role,
            school_id=school_id,
            details=entry_details,
        )
    
    def verify_chain(self) -> bool:
        """Verify integrity of audit chain.
        
        Returns:
            True if chain is valid, False if tampered
        """
        if not self._entries:
            return True
        
        expected_prev = "genesis"
        for entry in self._entries:
            if entry.previous_hash != expected_prev:
                logger.critical(
                    "AUDIT_CHAIN_VERIFICATION_FAILED",
                    extra={
                        "entry_id": entry.entry_id,
                        "expected_prev": expected_prev[:16],
                        "actual_prev": entry.previous_hash[:16],
                    }
                )
                return False
            
            computed = entry.compute_hash()
            if computed != entry.entry_hash:
                logger.critical(
                    "AUDIT_ENTRY_HASH_MISMATCH",
                    extra={
                        "entry_id": entry.entry_id,
                        "computed": computed[:16],
                        "stored": entry.entry_hash[:16],
                    }
                )
                return False
            
            expected_prev = entry.entry_hash
        
        logger.info(
            "AUDIT_CHAIN_VERIFIED",
            extra={"entry_count": len(self._entries)}
        )
        return True
    
    def query(
        self,
        entity_type: Optional[AuditEntity] = None,
        entity_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list:
        """Query audit entries.
        
        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            action: Filter by action
            start_date: Filter by start date
            end_date: Filter by end date
            
        Returns:
            List of matching AuditEntry objects
        """
        results = self._entries
        
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if entity_id:
            results = [e for e in results if e.entity_id == entity_id]
        if action:
            results = [e for e in results if e.action == action]
        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]
        
        return results
