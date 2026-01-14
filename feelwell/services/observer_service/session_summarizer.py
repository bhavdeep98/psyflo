"""Session summarizer - Layer 2 aggregation.

Generates SessionSummary after a conversation ends, aggregating
all messages and clinical markers from the session.
"""
import logging
from datetime import datetime
from typing import List, Optional

from feelwell.shared.models import (
    ClinicalMarker,
    CurrentSnapshot,
    SessionSummary,
    RiskLevel,
    ClinicalFramework,
)
from .clinical_markers import ClinicalMarkerDetector

logger = logging.getLogger(__name__)


class SessionSummarizer:
    """Generates Layer 2 session summaries from message snapshots.
    
    Called when a session ends to aggregate all analysis into
    a single summary for counselor review.
    """
    
    def __init__(self, marker_detector: Optional[ClinicalMarkerDetector] = None):
        """Initialize summarizer.
        
        Args:
            marker_detector: Clinical marker detector for score calculation
        """
        self.marker_detector = marker_detector or ClinicalMarkerDetector()
        
        logger.info("SESSION_SUMMARIZER_INITIALIZED")
    
    def summarize(
        self,
        session_id: str,
        student_id_hash: str,
        snapshots: List[CurrentSnapshot],
        session_start: datetime,
        session_end: datetime,
    ) -> SessionSummary:
        """Generate session summary from message snapshots.
        
        Args:
            session_id: Session identifier
            student_id_hash: Hashed student ID
            snapshots: List of CurrentSnapshot from the session
            session_start: Session start timestamp
            session_end: Session end timestamp
            
        Returns:
            SessionSummary with aggregated analysis
            
        Logs:
            - SESSION_SUMMARY_STARTED: Before summarization
            - SESSION_SUMMARY_COMPLETED: After summarization
        """
        logger.info(
            "SESSION_SUMMARY_STARTED",
            extra={
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "snapshot_count": len(snapshots),
            }
        )
        
        if not snapshots:
            return self._create_empty_summary(
                session_id, student_id_hash, session_start, session_end
            )
        
        # Calculate duration
        duration_minutes = int((session_end - session_start).total_seconds() / 60)
        
        # Extract risk trajectory
        start_risk = snapshots[0].risk_score
        end_risk = snapshots[-1].risk_score
        trajectory = self._calculate_trajectory(start_risk, end_risk)
        
        # Aggregate all markers
        all_markers = []
        for snapshot in snapshots:
            all_markers.extend(snapshot.markers)
        
        # Deduplicate markers by (framework, item_id)
        unique_markers = self._deduplicate_markers(all_markers)
        
        # Calculate clinical scores
        phq9_score = self.marker_detector.calculate_phq9_score(unique_markers)
        gad7_score = self.marker_detector.calculate_gad7_score(unique_markers)
        
        # Determine if counselor should be flagged
        counselor_flag = self._should_flag_counselor(
            end_risk, trajectory, phq9_score, unique_markers
        )
        
        summary = SessionSummary(
            session_id=session_id,
            student_id_hash=student_id_hash,
            duration_minutes=duration_minutes,
            message_count=len(snapshots),
            start_risk_score=start_risk,
            end_risk_score=end_risk,
            phq9_score=phq9_score,
            gad7_score=gad7_score,
            risk_trajectory=trajectory,
            counselor_flag=counselor_flag,
            markers_detected=unique_markers,
        )
        
        logger.info(
            "SESSION_SUMMARY_COMPLETED",
            extra={
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "duration_minutes": duration_minutes,
                "message_count": len(snapshots),
                "start_risk": start_risk,
                "end_risk": end_risk,
                "trajectory": trajectory,
                "phq9_score": phq9_score,
                "gad7_score": gad7_score,
                "counselor_flag": counselor_flag,
                "unique_marker_count": len(unique_markers),
            }
        )
        
        return summary
    
    def _calculate_trajectory(self, start: float, end: float) -> str:
        """Determine risk trajectory over session.
        
        Args:
            start: Starting risk score
            end: Ending risk score
            
        Returns:
            "stable", "improving", or "escalating"
        """
        delta = end - start
        
        if delta > 0.2:
            return "escalating"
        elif delta < -0.2:
            return "improving"
        else:
            return "stable"
    
    def _deduplicate_markers(
        self, 
        markers: List[ClinicalMarker]
    ) -> List[ClinicalMarker]:
        """Remove duplicate markers, keeping highest confidence.
        
        Args:
            markers: List of all markers from session
            
        Returns:
            Deduplicated list with highest confidence per item
        """
        best_markers = {}
        
        for marker in markers:
            key = (marker.framework, marker.item_id)
            if key not in best_markers or marker.confidence > best_markers[key].confidence:
                best_markers[key] = marker
        
        return list(best_markers.values())
    
    def _should_flag_counselor(
        self,
        end_risk: float,
        trajectory: str,
        phq9_score: Optional[int],
        markers: List[ClinicalMarker],
    ) -> bool:
        """Determine if session should be flagged for counselor review.
        
        Args:
            end_risk: Final risk score
            trajectory: Risk trajectory
            phq9_score: Estimated PHQ-9 score
            markers: Detected clinical markers
            
        Returns:
            True if counselor should review this session
        """
        # Flag if risk is elevated at end
        if end_risk >= 0.5:
            return True
        
        # Flag if trajectory is escalating
        if trajectory == "escalating":
            return True
        
        # Flag if PHQ-9 indicates moderate+ depression
        if phq9_score is not None and phq9_score >= 10:
            return True
        
        # Flag if self-harm marker detected (PHQ-9 Item 9)
        for marker in markers:
            if (marker.framework == ClinicalFramework.PHQ9 and 
                marker.item_id == 9):  # Self-harm item
                return True
        
        return False
    
    def _create_empty_summary(
        self,
        session_id: str,
        student_id_hash: str,
        session_start: datetime,
        session_end: datetime,
    ) -> SessionSummary:
        """Create summary for session with no messages.
        
        Args:
            session_id: Session identifier
            student_id_hash: Hashed student ID
            session_start: Session start timestamp
            session_end: Session end timestamp
            
        Returns:
            Empty SessionSummary
        """
        duration = int((session_end - session_start).total_seconds() / 60)
        
        return SessionSummary(
            session_id=session_id,
            student_id_hash=student_id_hash,
            duration_minutes=duration,
            message_count=0,
            start_risk_score=0.0,
            end_risk_score=0.0,
            risk_trajectory="stable",
            counselor_flag=False,
        )
