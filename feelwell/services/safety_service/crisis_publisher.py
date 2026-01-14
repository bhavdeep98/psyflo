"""Crisis event publisher for Safety Service.

Publishes crisis events to Kinesis stream for decoupled processing.
Per ADR-004: Crisis events go to Kinesis/EventBridge, not direct service calls.

This ensures the "fire alarm" works even if other services are down.
The Crisis Engine consumes these events and orchestrates the response.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SafetyCrisisEvent:
    """Immutable crisis event from Safety Service.
    
    Published to Kinesis for Crisis Engine consumption.
    """
    event_id: str
    event_type: str = "safety.crisis.detected"
    message_id: str = ""
    session_id: str = ""
    student_id_hash: str = ""
    school_id: Optional[str] = None
    risk_level: str = "CRISIS"
    risk_score: float = 1.0
    matched_keywords: List[str] = field(default_factory=list)
    trigger_source: str = "safety_service"
    requires_human_intervention: bool = True
    escalation_path: str = "counselor_alert"
    scanner_version: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_kinesis_payload(self) -> dict:
        """Convert to Kinesis record payload.
        
        Returns:
            Dictionary for Kinesis put_record Data field
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat() + "Z",
            "source": "safety-service",
            "data": {
                "message_id": self.message_id,
                "session_id": self.session_id,
                "student_id_hash": self.student_id_hash,
                "school_id": self.school_id,
                "risk_level": self.risk_level,
                "risk_score": self.risk_score,
                "matched_keywords": self.matched_keywords,
                "trigger_source": self.trigger_source,
                "requires_human_intervention": self.requires_human_intervention,
                "escalation_path": self.escalation_path,
                "scanner_version": self.scanner_version,
            }
        }


class CrisisEventPublisher:
    """Publishes crisis events to Kinesis stream.
    
    Decoupled from Crisis Engine - publishes events that the
    Crisis Engine consumes asynchronously.
    
    Failure Handling:
        - Publishing failure does NOT block the safety response
        - LLM bypass still happens even if publish fails
        - Failures are logged at CRITICAL level for alerting
    """
    
    def __init__(
        self,
        stream_name: str = "feelwell-crisis-events",
        enabled: bool = True,
        region: Optional[str] = None,
    ):
        """Initialize publisher.
        
        Args:
            stream_name: Kinesis stream name
            enabled: Whether publishing is enabled (disable for local dev)
            region: AWS region (defaults to AWS_REGION env var)
        """
        self.stream_name = stream_name
        self.enabled = enabled
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self._kinesis_client = None
        
        logger.info(
            "CRISIS_PUBLISHER_INITIALIZED",
            extra={
                "stream_name": stream_name,
                "enabled": enabled,
                "region": self.region,
            }
        )
    
    @property
    def kinesis_client(self):
        """Lazy initialization of Kinesis client."""
        if self._kinesis_client is None and self.enabled:
            try:
                import boto3
                self._kinesis_client = boto3.client(
                    "kinesis",
                    region_name=self.region,
                )
            except Exception as e:
                logger.error(
                    "KINESIS_CLIENT_INIT_FAILED",
                    extra={"error": str(e)}
                )
        return self._kinesis_client

    def publish_crisis(
        self,
        message_id: str,
        session_id: str,
        student_id_hash: str,
        matched_keywords: List[str],
        risk_score: float,
        scanner_version: str,
        school_id: Optional[str] = None,
    ) -> bool:
        """Publish a crisis event to Kinesis.
        
        Args:
            message_id: Message that triggered crisis
            session_id: Current session ID
            student_id_hash: Hashed student identifier (ADR-003)
            matched_keywords: Crisis keywords that were matched
            risk_score: Risk score from scanner
            scanner_version: Scanner version for audit
            school_id: School identifier for routing
            
        Returns:
            True if published successfully, False otherwise
            
        Note:
            Failure does NOT raise exception - LLM bypass still happens.
            Failures are logged at CRITICAL level for alerting.
        """
        if not self.enabled:
            logger.info(
                "CRISIS_PUBLISH_SKIPPED",
                extra={
                    "message_id": message_id,
                    "reason": "publishing_disabled",
                }
            )
            return False
        
        # Create event
        event = SafetyCrisisEvent(
            event_id=f"evt_{uuid.uuid4().hex[:12]}",
            message_id=message_id,
            session_id=session_id,
            student_id_hash=student_id_hash,
            school_id=school_id,
            risk_score=risk_score,
            matched_keywords=matched_keywords,
            scanner_version=scanner_version,
        )
        
        payload = event.to_kinesis_payload()
        
        logger.info(
            "CRISIS_EVENT_PUBLISHING",
            extra={
                "event_id": event.event_id,
                "message_id": message_id,
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "school_id": school_id,
            }
        )
        
        try:
            if self.kinesis_client is None:
                # Fallback: Log event for manual processing
                logger.critical(
                    "CRISIS_EVENT_FALLBACK_LOG",
                    extra={
                        "event_id": event.event_id,
                        "payload": json.dumps(payload),
                        "reason": "kinesis_client_unavailable",
                        "action": "MANUAL_PROCESSING_REQUIRED",
                    }
                )
                return False
            
            # Publish to Kinesis
            response = self.kinesis_client.put_record(
                StreamName=self.stream_name,
                Data=json.dumps(payload),
                PartitionKey=student_id_hash,  # Same student → same shard
            )
            
            logger.critical(
                "CRISIS_EVENT_PUBLISHED",
                extra={
                    "event_id": event.event_id,
                    "message_id": message_id,
                    "session_id": session_id,
                    "student_id_hash": student_id_hash,
                    "school_id": school_id,
                    "shard_id": response.get("ShardId"),
                    "sequence_number": response.get("SequenceNumber"),
                }
            )
            return True
            
        except Exception as e:
            # CRITICAL: Log failure but don't raise
            # LLM bypass still happens - this is just notification
            logger.critical(
                "CRISIS_EVENT_PUBLISH_FAILED",
                extra={
                    "event_id": event.event_id,
                    "message_id": message_id,
                    "session_id": session_id,
                    "student_id_hash": student_id_hash,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "action": "MANUAL_REVIEW_REQUIRED",
                    "payload": json.dumps(payload),
                }
            )
            return False
    
    def publish_batch(
        self,
        events: List[SafetyCrisisEvent],
    ) -> int:
        """Publish multiple crisis events in batch.
        
        Args:
            events: List of SafetyCrisisEvent to publish
            
        Returns:
            Number of successfully published events
        """
        if not self.enabled or not events:
            return 0
        
        if self.kinesis_client is None:
            logger.error(
                "CRISIS_BATCH_PUBLISH_FAILED",
                extra={"reason": "kinesis_client_unavailable"}
            )
            return 0
        
        records = [
            {
                "Data": json.dumps(event.to_kinesis_payload()),
                "PartitionKey": event.student_id_hash,
            }
            for event in events
        ]
        
        try:
            response = self.kinesis_client.put_records(
                StreamName=self.stream_name,
                Records=records,
            )
            
            failed_count = response.get("FailedRecordCount", 0)
            success_count = len(events) - failed_count
            
            logger.info(
                "CRISIS_BATCH_PUBLISHED",
                extra={
                    "total": len(events),
                    "success": success_count,
                    "failed": failed_count,
                }
            )
            
            return success_count
            
        except Exception as e:
            logger.critical(
                "CRISIS_BATCH_PUBLISH_FAILED",
                extra={
                    "error": str(e),
                    "event_count": len(events),
                }
            )
            return 0
