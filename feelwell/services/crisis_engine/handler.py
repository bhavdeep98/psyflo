"""Crisis event handler - orchestrates escalation flow.

Receives crisis events from Safety Service and Observer Service,
determines escalation path, and coordinates response.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid

from feelwell.shared.models import RiskLevel
from .events import (
    CrisisEvent,
    CrisisEventType,
    CrisisEventPublisher,
    EscalationPath,
)

logger = logging.getLogger(__name__)


class CrisisState(Enum):
    """State machine for crisis event lifecycle."""
    DETECTED = "detected"
    NOTIFYING = "notifying"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"  # Escalated to higher authority


@dataclass
class CrisisRecord:
    """Mutable record tracking crisis event state.
    
    Stored in DynamoDB for fast writes and state tracking.
    """
    crisis_id: str
    event_id: str
    student_id_hash: str
    session_id: str
    school_id: Optional[str]
    state: CrisisState
    escalation_path: EscalationPath
    trigger_source: str
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None


class CrisisHandler:
    """Handles crisis events and orchestrates response.
    
    This is the "kill switch" - when triggered, it bypasses
    all normal chat flow and activates emergency protocols.
    """
    
    def __init__(
        self,
        event_publisher: Optional[CrisisEventPublisher] = None,
    ):
        """Initialize handler with dependencies.
        
        Args:
            event_publisher: Publisher for downstream events
        """
        self.event_publisher = event_publisher or CrisisEventPublisher()
        self._active_crises: dict = {}  # In-memory for dev; DynamoDB in prod
        
        logger.info("CRISIS_HANDLER_INITIALIZED")
    
    def handle_safety_crisis(
        self,
        student_id_hash: str,
        session_id: str,
        matched_keywords: list,
        school_id: Optional[str] = None,
    ) -> CrisisRecord:
        """Handle crisis detected by Safety Service.
        
        This is the highest priority path - Safety Service detected
        explicit crisis language that bypassed the LLM entirely.
        
        Args:
            student_id_hash: Hashed student identifier
            session_id: Current session ID
            matched_keywords: Crisis keywords that triggered detection
            school_id: School identifier for routing
            
        Returns:
            CrisisRecord tracking the event
            
        Logs:
            - CRISIS_HANDLER_SAFETY_TRIGGERED: On entry (critical)
            - CRISIS_RECORD_CREATED: After record creation
        """
        logger.critical(
            "CRISIS_HANDLER_SAFETY_TRIGGERED",
            extra={
                "student_id_hash": student_id_hash,
                "session_id": session_id,
                "keyword_count": len(matched_keywords),
                "school_id": school_id,
                "action": "IMMEDIATE_ESCALATION",
            }
        )
        
        # Create crisis event
        event = self.event_publisher.create_crisis_event(
            student_id_hash=student_id_hash,
            session_id=session_id,
            trigger_source="safety_service",
            trigger_keywords=matched_keywords,
            school_id=school_id,
        )
        
        # Create tracking record
        record = CrisisRecord(
            crisis_id=f"crisis_{uuid.uuid4().hex[:12]}",
            event_id=event.event_id,
            student_id_hash=student_id_hash,
            session_id=session_id,
            school_id=school_id,
            state=CrisisState.DETECTED,
            escalation_path=EscalationPath.COUNSELOR_ALERT,
            trigger_source="safety_service",
            created_at=datetime.utcnow(),
        )
        
        # Store record
        self._active_crises[record.crisis_id] = record
        
        logger.info(
            "CRISIS_RECORD_CREATED",
            extra={
                "crisis_id": record.crisis_id,
                "event_id": event.event_id,
                "student_id_hash": student_id_hash,
                "state": record.state.value,
            }
        )
        
        # Publish event to stream
        self.event_publisher.publish(event)
        
        # Update state to notifying
        record.state = CrisisState.NOTIFYING
        
        return record
    
    def handle_observer_threshold(
        self,
        student_id_hash: str,
        session_id: str,
        risk_score: float,
        phq9_score: Optional[int] = None,
        school_id: Optional[str] = None,
    ) -> CrisisRecord:
        """Handle threshold exceeded from Observer Service.
        
        This path is triggered when clinical markers indicate
        elevated risk, even without explicit crisis language.
        
        Args:
            student_id_hash: Hashed student identifier
            session_id: Current session ID
            risk_score: Risk score that exceeded threshold
            phq9_score: PHQ-9 score if available
            school_id: School identifier for routing
            
        Returns:
            CrisisRecord tracking the event
        """
        logger.critical(
            "CRISIS_HANDLER_OBSERVER_TRIGGERED",
            extra={
                "student_id_hash": student_id_hash,
                "session_id": session_id,
                "risk_score": risk_score,
                "phq9_score": phq9_score,
                "school_id": school_id,
                "action": "THRESHOLD_ESCALATION",
            }
        )
        
        # Create event
        event = CrisisEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=CrisisEventType.OBSERVER_THRESHOLD_EXCEEDED,
            student_id_hash=student_id_hash,
            session_id=session_id,
            risk_level="CRISIS",
            trigger_source="observer_service",
            trigger_keywords=[],
            requires_human_intervention=True,
            escalation_path=EscalationPath.COUNSELOR_ALERT,
            school_id=school_id,
        )
        
        # Create tracking record
        record = CrisisRecord(
            crisis_id=f"crisis_{uuid.uuid4().hex[:12]}",
            event_id=event.event_id,
            student_id_hash=student_id_hash,
            session_id=session_id,
            school_id=school_id,
            state=CrisisState.DETECTED,
            escalation_path=EscalationPath.COUNSELOR_ALERT,
            trigger_source="observer_service",
            created_at=datetime.utcnow(),
        )
        
        self._active_crises[record.crisis_id] = record
        self.event_publisher.publish(event)
        record.state = CrisisState.NOTIFYING
        
        return record
    
    def acknowledge(
        self,
        crisis_id: str,
        acknowledged_by: str,
    ) -> Optional[CrisisRecord]:
        """Acknowledge a crisis event.
        
        Called when a counselor acknowledges they've seen the alert.
        
        Args:
            crisis_id: Crisis record identifier
            acknowledged_by: User ID of acknowledging counselor
            
        Returns:
            Updated CrisisRecord or None if not found
        """
        record = self._active_crises.get(crisis_id)
        if not record:
            logger.warning(
                "CRISIS_ACKNOWLEDGE_NOT_FOUND",
                extra={"crisis_id": crisis_id}
            )
            return None
        
        record.state = CrisisState.ACKNOWLEDGED
        record.acknowledged_at = datetime.utcnow()
        record.acknowledged_by = acknowledged_by
        
        logger.info(
            "CRISIS_ACKNOWLEDGED",
            extra={
                "crisis_id": crisis_id,
                "acknowledged_by": acknowledged_by,
                "student_id_hash": record.student_id_hash,
                "time_to_acknowledge_seconds": (
                    record.acknowledged_at - record.created_at
                ).total_seconds(),
            }
        )
        
        return record
    
    def resolve(
        self,
        crisis_id: str,
        resolved_by: str,
        resolution_notes: str,
    ) -> Optional[CrisisRecord]:
        """Resolve a crisis event.
        
        Called when a counselor has addressed the crisis.
        
        Args:
            crisis_id: Crisis record identifier
            resolved_by: User ID of resolving counselor
            resolution_notes: Notes on how crisis was resolved
            
        Returns:
            Updated CrisisRecord or None if not found
        """
        record = self._active_crises.get(crisis_id)
        if not record:
            logger.warning(
                "CRISIS_RESOLVE_NOT_FOUND",
                extra={"crisis_id": crisis_id}
            )
            return None
        
        record.state = CrisisState.RESOLVED
        record.resolved_at = datetime.utcnow()
        record.resolved_by = resolved_by
        record.resolution_notes = resolution_notes
        
        logger.info(
            "CRISIS_RESOLVED",
            extra={
                "crisis_id": crisis_id,
                "resolved_by": resolved_by,
                "student_id_hash": record.student_id_hash,
                "time_to_resolve_seconds": (
                    record.resolved_at - record.created_at
                ).total_seconds(),
            }
        )
        
        return record
    
    def get_active_crises(self, school_id: Optional[str] = None) -> list:
        """Get all active (unresolved) crisis records.
        
        Args:
            school_id: Filter by school if provided
            
        Returns:
            List of active CrisisRecord objects
        """
        active = [
            r for r in self._active_crises.values()
            if r.state != CrisisState.RESOLVED
        ]
        
        if school_id:
            active = [r for r in active if r.school_id == school_id]
        
        return active
