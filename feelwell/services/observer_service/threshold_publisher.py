"""Threshold event publisher for Observer Service.

Publishes threshold exceeded events to Kinesis when risk is elevated.
Per ADR-004: Events go to Kinesis/EventBridge, not direct service calls.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ThresholdEvent:
    """Immutable threshold exceeded event."""
    event_id: str
    event_type: str = "observer.threshold.exceeded"
    message_id: str = ""
    session_id: str = ""
    student_id_hash: str = ""
    school_id: Optional[str] = None
    risk_level: str = "CAUTION"
    risk_score: float = 0.0
    phq9_score: Optional[int] = None
    trigger_source: str = "observer_service"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_kinesis_payload(self) -> dict:
        """Convert to Kinesis record payload."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() + "Z",
            "source": "observer-service",
            "data": {
                "message_id": self.message_id,
                "session_id": self.session_id,
                "student_id_hash": self.student_id_hash,
                "school_id": self.school_id,
                "risk_level": self.risk_level,
                "risk_score": self.risk_score,
                "phq9_score": self.phq9_score,
                "trigger_source": self.trigger_source,
            }
        }


class ThresholdEventPublisher:
    """Publishes threshold exceeded events to Kinesis."""
    
    def __init__(
        self,
        stream_name: str = "feelwell-crisis-events",
        enabled: bool = True,
        region: Optional[str] = None,
    ):
        self.stream_name = stream_name
        self.enabled = enabled
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._kinesis_client = None
        
        logger.info(
            "THRESHOLD_PUBLISHER_INITIALIZED",
            extra={"stream_name": stream_name, "enabled": enabled}
        )
    
    @property
    def kinesis_client(self):
        """Lazy initialization of Kinesis client."""
        if self._kinesis_client is None and self.enabled:
            try:
                import boto3
                self._kinesis_client = boto3.client("kinesis", region_name=self.region)
            except Exception as e:
                logger.error("KINESIS_CLIENT_INIT_FAILED", extra={"error": str(e)})
        return self._kinesis_client
    
    def publish_threshold_event(
        self,
        message_id: str,
        session_id: str,
        student_id_hash: str,
        risk_level: str,
        risk_score: float,
        phq9_score: Optional[int] = None,
        school_id: Optional[str] = None,
    ) -> bool:
        """Publish threshold exceeded event."""
        if not self.enabled:
            logger.info("THRESHOLD_PUBLISH_SKIPPED", extra={"reason": "disabled"})
            return False
        
        event = ThresholdEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            message_id=message_id,
            session_id=session_id,
            student_id_hash=student_id_hash,
            school_id=school_id,
            risk_level=risk_level,
            risk_score=risk_score,
            phq9_score=phq9_score,
        )
        
        payload = event.to_kinesis_payload()
        
        try:
            if self.kinesis_client is None:
                logger.warning(
                    "THRESHOLD_EVENT_FALLBACK_LOG",
                    extra={"event_id": event.event_id, "payload": json.dumps(payload)}
                )
                return False
            
            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(payload),
                PartitionKey=student_id_hash,
            )
            
            logger.info(
                "THRESHOLD_EVENT_PUBLISHED",
                extra={
                    "event_id": event.event_id,
                    "risk_level": risk_level,
                    "shard_id": response.get("ShardId"),
                }
            )
            return True
            
        except Exception as e:
            logger.error(
                "THRESHOLD_EVENT_PUBLISH_FAILED",
                extra={"event_id": event.event_id, "error": str(e)}
            )
            return False
