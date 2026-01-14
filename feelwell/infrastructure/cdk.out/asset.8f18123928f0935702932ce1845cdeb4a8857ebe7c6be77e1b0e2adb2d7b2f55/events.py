"""Crisis event definitions and publishing.

Per ADR-004: Crisis events publish to Kinesis/EventBridge,
not direct service calls. This ensures the "fire alarm" works
even if other services are down.
"""
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Optional
import uuid

logger = logging.getLogger(__name__)


class CrisisEventType(Enum):
    """Types of crisis events that trigger escalation."""
    SAFETY_CRISIS_DETECTED = "safety.crisis.detected"
    OBSERVER_THRESHOLD_EXCEEDED = "observer.threshold.exceeded"
    CRISIS_ACKNOWLEDGED = "crisis.acknowledged"
    CRISIS_RESOLVED = "crisis.resolved"


class EscalationPath(Enum):
    """Escalation paths based on severity and context."""
    COUNSELOR_ALERT = "counselor_alert"      # Notify school counselor
    ADMIN_ALERT = "admin_alert"              # Notify school admin
    EMERGENCY_SERVICES = "emergency_services" # 911 / crisis hotline
    PARENT_NOTIFICATION = "parent_notification"


@dataclass(frozen=True)
class CrisisEvent:
    """Immutable crisis event for the event stream.
    
    Published to Kinesis/EventBridge for decoupled processing.
    """
    event_id: str
    event_type: CrisisEventType
    student_id_hash: str
    session_id: str
    risk_level: str
    trigger_source: str  # "safety_service" or "observer_service"
    trigger_keywords: List[str] = field(default_factory=list)
    requires_human_intervention: bool = True
    escalation_path: EscalationPath = EscalationPath.COUNSELOR_ALERT
    school_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_event_payload(self) -> dict:
        """Convert to event stream payload format.
        
        Returns:
            Dictionary suitable for Kinesis/EventBridge
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp.isoformat() + "Z",
            "source": "crisis-engine",
            "data": {
                "student_id_hash": self.student_id_hash,
                "session_id": self.session_id,
                "risk_level": self.risk_level,
                "trigger_source": self.trigger_source,
                "trigger_keywords": self.trigger_keywords,
                "requires_human_intervention": self.requires_human_intervention,
                "escalation_path": self.escalation_path.value,
                "school_id": self.school_id,
            }
        }


class CrisisEventPublisher:
    """Publishes crisis events to the event stream.
    
    In production, this would use boto3 to publish to Kinesis.
    Abstracted here for testability.
    """
    
    def __init__(self, stream_name: str = "feelwell-crisis-events"):
        """Initialize publisher.
        
        Args:
            stream_name: Kinesis stream name
        """
        self.stream_name = stream_name
        self._kinesis_client = None  # Lazy initialization
        
        logger.info(
            "CRISIS_EVENT_PUBLISHER_INITIALIZED",
            extra={"stream_name": stream_name}
        )
    
    def publish(self, event: CrisisEvent) -> bool:
        """Publish a crisis event to the stream.
        
        Args:
            event: CrisisEvent to publish
            
        Returns:
            True if published successfully
            
        Logs:
            - CRISIS_EVENT_PUBLISHING: Before publish
            - CRISIS_EVENT_PUBLISHED: After successful publish
            - CRISIS_EVENT_PUBLISH_FAILED: On failure (critical)
        """
        payload = event.to_event_payload()
        
        logger.info(
            "CRISIS_EVENT_PUBLISHING",
            extra={
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "student_id_hash": event.student_id_hash,
                "escalation_path": event.escalation_path.value,
            }
        )
        
        try:
            # In production: self._kinesis_client.put_record(...)
            # For now, log the event for development
            logger.critical(
                "CRISIS_EVENT_PUBLISHED",
                extra={
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "student_id_hash": event.student_id_hash,
                    "session_id": event.session_id,
                    "escalation_path": event.escalation_path.value,
                    "requires_human_intervention": event.requires_human_intervention,
                    "payload": json.dumps(payload),
                }
            )
            return True
            
        except Exception as e:
            logger.critical(
                "CRISIS_EVENT_PUBLISH_FAILED",
                extra={
                    "event_id": event.event_id,
                    "error": str(e),
                    "action": "RETRY_WITH_FALLBACK",
                }
            )
            return False
    
    def create_crisis_event(
        self,
        student_id_hash: str,
        session_id: str,
        trigger_source: str,
        trigger_keywords: Optional[List[str]] = None,
        school_id: Optional[str] = None,
    ) -> CrisisEvent:
        """Factory method to create a crisis event.
        
        Args:
            student_id_hash: Hashed student identifier
            session_id: Current session ID
            trigger_source: Service that detected the crisis
            trigger_keywords: Keywords that triggered detection
            school_id: School identifier for routing
            
        Returns:
            New CrisisEvent ready for publishing
        """
        return CrisisEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            event_type=CrisisEventType.SAFETY_CRISIS_DETECTED,
            student_id_hash=student_id_hash,
            session_id=session_id,
            risk_level="CRISIS",
            trigger_source=trigger_source,
            trigger_keywords=trigger_keywords or [],
            requires_human_intervention=True,
            escalation_path=EscalationPath.COUNSELOR_ALERT,
            school_id=school_id,
        )
