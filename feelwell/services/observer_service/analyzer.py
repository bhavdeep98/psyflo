"""Message analyzer - Layer 1 real-time analysis.

Analyzes each message as it arrives, generating CurrentSnapshot
for immediate risk assessment.
"""
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import uuid

from feelwell.shared.models import (
    ClinicalMarker,
    CurrentSnapshot,
    RiskLevel,
)
from feelwell.shared.utils import hash_pii
from .clinical_markers import ClinicalMarkerDetector
from .sentiment_analyzer import BERTSentimentAnalyzer, SentimentLabel

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalysisConfig:
    """Configuration for message analysis."""
    # Risk score weights
    marker_weight: float = 0.4
    sentiment_weight: float = 0.3
    keyword_weight: float = 0.3
    
    # Thresholds
    caution_threshold: float = 0.4
    crisis_threshold: float = 0.7
    
    # BERT configuration
    bert_enabled: bool = False  # Disabled by default for latency


class MessageAnalyzer:
    """Real-time message analyzer for Layer 1 risk assessment.
    
    Generates CurrentSnapshot for each message, combining:
    - Clinical marker detection (PHQ-9, GAD-7)
    - BERT sentiment analysis (optional)
    - Risk score calculation
    - Risk level classification
    """
    
    def __init__(
        self,
        config: Optional[AnalysisConfig] = None,
        marker_detector: Optional[ClinicalMarkerDetector] = None,
        sentiment_analyzer: Optional[BERTSentimentAnalyzer] = None,
    ):
        """Initialize analyzer with dependencies.
        
        Args:
            config: Analysis configuration
            marker_detector: Clinical marker detector (injected for testing)
            sentiment_analyzer: BERT sentiment analyzer (injected for testing)
        """
        self.config = config or AnalysisConfig()
        self.marker_detector = marker_detector or ClinicalMarkerDetector()
        
        # Initialize BERT if enabled
        bert_enabled = self.config.bert_enabled or os.getenv("BERT_ENABLED", "false").lower() == "true"
        if sentiment_analyzer is not None:
            self.sentiment_analyzer = sentiment_analyzer
        elif bert_enabled:
            self.sentiment_analyzer = BERTSentimentAnalyzer(enabled=True)
        else:
            self.sentiment_analyzer = None
        
        logger.info(
            "MESSAGE_ANALYZER_INITIALIZED",
            extra={
                "caution_threshold": self.config.caution_threshold,
                "crisis_threshold": self.config.crisis_threshold,
                "bert_enabled": self.sentiment_analyzer is not None and self.sentiment_analyzer.is_available,
            }
        )
    
    def analyze(
        self,
        message_id: str,
        session_id: str,
        student_id: str,
        text: str,
        safety_risk_score: float = 0.0,
    ) -> CurrentSnapshot:
        """Analyze a single message and generate risk snapshot.
        
        This is the main entry point for Layer 1 analysis.
        Called asynchronously after Safety Service clears the message.
        
        Args:
            message_id: Unique message identifier
            session_id: Current conversation session ID
            student_id: Student identifier (will be hashed)
            text: Message text to analyze
            safety_risk_score: Risk score from Safety Service (0.0-1.0)
            
        Returns:
            CurrentSnapshot with risk assessment
            
        Logs:
            - ANALYSIS_STARTED: Before analysis begins
            - ANALYSIS_COMPLETED: After analysis finishes
        """
        start_time = time.perf_counter()
        student_id_hash = hash_pii(student_id)
        
        logger.info(
            "ANALYSIS_STARTED",
            extra={
                "message_id": message_id,
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "text_length": len(text),
            }
        )
        
        # Detect clinical markers
        markers = self.marker_detector.detect(text)
        
        # Run BERT sentiment analysis if enabled
        sentiment_score = 0.0
        sentiment_label = None
        if self.sentiment_analyzer and self.sentiment_analyzer.is_available:
            sentiment_result = self.sentiment_analyzer.analyze(text)
            sentiment_score = sentiment_result.risk_contribution
            sentiment_label = sentiment_result.label.value
        
        # Calculate composite risk score
        risk_score = self._calculate_risk_score(
            markers=markers,
            safety_score=safety_risk_score,
            sentiment_score=sentiment_score,
        )
        
        # Determine risk level
        risk_level = self._determine_risk_level(risk_score)
        
        snapshot = CurrentSnapshot(
            message_id=message_id,
            session_id=session_id,
            student_id_hash=student_id_hash,
            risk_score=risk_score,
            risk_level=risk_level,
            markers=markers,
        )
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            "ANALYSIS_COMPLETED",
            extra={
                "message_id": message_id,
                "session_id": session_id,
                "student_id_hash": student_id_hash,
                "risk_score": risk_score,
                "risk_level": risk_level.value,
                "marker_count": len(markers),
                "sentiment_label": sentiment_label,
                "sentiment_score": sentiment_score,
                "latency_ms": latency_ms,
            }
        )
        
        return snapshot
    
    def _calculate_risk_score(
        self,
        markers: list,
        safety_score: float,
        sentiment_score: float = 0.0,
    ) -> float:
        """Calculate composite risk score from multiple signals.
        
        Args:
            markers: Detected clinical markers
            safety_score: Risk score from Safety Service
            sentiment_score: Risk contribution from BERT sentiment
            
        Returns:
            Composite risk score (0.0-1.0)
        """
        # Marker-based score
        marker_score = 0.0
        if markers:
            # Weight by confidence and count
            total_confidence = sum(m.confidence for m in markers)
            marker_score = min(total_confidence / 3.0, 1.0)  # Normalize
        
        # Combine scores with weights
        composite = (
            marker_score * self.config.marker_weight +
            safety_score * self.config.keyword_weight +
            max(sentiment_score, 0.0) * self.config.sentiment_weight  # Only positive contributions
        )
        
        # Normalize to 0.0-1.0
        return min(max(composite, 0.0), 1.0)
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Map risk score to risk level.
        
        Args:
            risk_score: Calculated risk score
            
        Returns:
            Appropriate RiskLevel enum value
        """
        if risk_score >= self.config.crisis_threshold:
            return RiskLevel.CRISIS
        elif risk_score >= self.config.caution_threshold:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.SAFE
