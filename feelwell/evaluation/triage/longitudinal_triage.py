"""Longitudinal triage evaluation - long-term pattern analysis.

Tests the system's ability to detect patterns across multiple sessions
over days/weeks/months. Uses RAG for historical context retrieval.

Metrics:
- Pattern Detection Rate: % of known patterns correctly identified
- Early Warning Accuracy: Predictions of future escalation
- Trend Correlation: Correlation between predicted and actual trajectories
- RAG Retrieval Quality: Relevance of retrieved historical context
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import uuid
import statistics

from feelwell.shared.utils import hash_pii

logger = logging.getLogger(__name__)


class LongitudinalPattern(Enum):
    """Known longitudinal risk patterns."""
    CHRONIC_LOW = "chronic_low"  # Persistent low-level distress
    GRADUAL_DECLINE = "gradual_decline"  # Slow escalation over weeks
    ACUTE_CRISIS = "acute_crisis"  # Sudden severe episode
    CYCLICAL = "cyclical"  # Recurring patterns (e.g., weekly)
    RECOVERY = "recovery"  # Improving trajectory
    STABLE_HEALTHY = "stable_healthy"  # Consistently low risk
    SEASONAL = "seasonal"  # Time-of-year patterns


@dataclass
class StudentHistory:
    """Historical data for a student across sessions."""
    student_id_hash: str
    sessions: List[Dict[str, Any]]
    first_session: datetime
    last_session: datetime
    total_messages: int
    crisis_count: int
    avg_risk_score: float
    risk_trajectory: List[float]  # Risk scores over time
    known_pattern: Optional[LongitudinalPattern] = None
    
    @property
    def duration_days(self) -> int:
        return (self.last_session - self.first_session).days
    
    @property
    def session_count(self) -> int:
        return len(self.sessions)


@dataclass
class PatternPrediction:
    """Prediction of longitudinal pattern."""
    student_id_hash: str
    predicted_pattern: LongitudinalPattern
    confidence: float
    risk_factors: List[str]
    recommended_intervention: str
    early_warning_score: float  # 0-1, likelihood of escalation
    supporting_evidence: List[str]


@dataclass
class LongitudinalMetrics:
    """Metrics for longitudinal triage evaluation."""
    total_students: int = 0
    
    # Pattern detection
    patterns_expected: int = 0
    patterns_correct: int = 0
    
    # Early warning
    escalations_predicted: int = 0
    escalations_actual: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    # RAG quality
    retrieval_relevance_scores: List[float] = field(default_factory=list)
    
    @property
    def pattern_accuracy(self) -> float:
        if self.patterns_expected == 0:
            return 0.0
        return self.patterns_correct / self.patterns_expected
    
    @property
    def early_warning_precision(self) -> float:
        """Of predicted escalations, how many actually escalated."""
        if self.escalations_predicted == 0:
            return 0.0
        return self.true_positives / self.escalations_predicted
    
    @property
    def early_warning_recall(self) -> float:
        """Of actual escalations, how many were predicted."""
        if self.escalations_actual == 0:
            return 1.0
        return self.true_positives / self.escalations_actual
    
    @property
    def avg_retrieval_relevance(self) -> float:
        if not self.retrieval_relevance_scores:
            return 0.0
        return statistics.mean(self.retrieval_relevance_scores)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_students": self.total_students,
            "pattern_accuracy": round(self.pattern_accuracy, 4),
            "early_warning_precision": round(self.early_warning_precision, 4),
            "early_warning_recall": round(self.early_warning_recall, 4),
            "avg_retrieval_relevance": round(self.avg_retrieval_relevance, 4),
        }


@dataclass
class LongitudinalTriageResult:
    """Result of longitudinal triage evaluation."""
    run_id: str
    started_at: datetime
    completed_at: datetime
    metrics: LongitudinalMetrics
    predictions: List[PatternPrediction]
    missed_patterns: List[str]
    false_alarms: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "metrics": self.metrics.to_dict(),
            "missed_pattern_ids": self.missed_patterns,
            "false_alarm_ids": self.false_alarms,
        }


class LongitudinalTriageEvaluator:
    """Evaluates long-term pattern detection and early warning.
    
    Uses RAG to retrieve relevant historical context and
    detect patterns across multiple sessions over time.
    """
    
    def __init__(
        self,
        vector_store=None,
        pattern_analyzer=None,
    ):
        """Initialize evaluator.
        
        Args:
            vector_store: Vector store for RAG retrieval
            pattern_analyzer: Pattern analysis component
        """
        self.vector_store = vector_store
        self.pattern_analyzer = pattern_analyzer
        
        logger.info("LONGITUDINAL_TRIAGE_EVALUATOR_INITIALIZED")
    
    def generate_synthetic_history(
        self,
        pattern: LongitudinalPattern,
        duration_days: int = 30,
        sessions_per_week: float = 2.5,
    ) -> StudentHistory:
        """Generate synthetic student history for testing.
        
        Args:
            pattern: The pattern to simulate
            duration_days: Duration of history
            sessions_per_week: Average sessions per week
            
        Returns:
            StudentHistory with simulated data
        """
        student_id_hash = hash_pii(f"synthetic_{uuid.uuid4().hex[:8]}")
        
        num_sessions = int((duration_days / 7) * sessions_per_week)
        sessions = []
        risk_trajectory = []
        
        base_time = datetime.utcnow() - timedelta(days=duration_days)
        crisis_count = 0
        total_messages = 0
        
        for i in range(num_sessions):
            session_time = base_time + timedelta(days=(i * duration_days / num_sessions))
            
            # Generate risk score based on pattern
            risk_score = self._generate_risk_for_pattern(pattern, i, num_sessions)
            risk_trajectory.append(risk_score)
            
            if risk_score >= 0.8:
                crisis_count += 1
            
            msg_count = 5 + (i % 10)  # Varying message counts
            total_messages += msg_count
            
            sessions.append({
                "session_id": f"sess_{i}",
                "timestamp": session_time,
                "risk_score": risk_score,
                "message_count": msg_count,
                "phq9_score": int(risk_score * 20),
                "counselor_flag": risk_score > 0.6,
            })
        
        return StudentHistory(
            student_id_hash=student_id_hash,
            sessions=sessions,
            first_session=base_time,
            last_session=sessions[-1]["timestamp"] if sessions else base_time,
            total_messages=total_messages,
            crisis_count=crisis_count,
            avg_risk_score=statistics.mean(risk_trajectory) if risk_trajectory else 0.0,
            risk_trajectory=risk_trajectory,
            known_pattern=pattern,
        )
    
    def _generate_risk_for_pattern(
        self,
        pattern: LongitudinalPattern,
        session_idx: int,
        total_sessions: int,
    ) -> float:
        """Generate risk score based on pattern type.
        
        Args:
            pattern: Pattern to simulate
            session_idx: Current session index
            total_sessions: Total number of sessions
            
        Returns:
            Risk score between 0 and 1
        """
        progress = session_idx / max(total_sessions - 1, 1)
        
        if pattern == LongitudinalPattern.STABLE_HEALTHY:
            return 0.1 + (0.1 * (session_idx % 3) / 3)  # Low, slight variation
        
        elif pattern == LongitudinalPattern.CHRONIC_LOW:
            return 0.3 + (0.1 * (session_idx % 5) / 5)  # Persistent moderate
        
        elif pattern == LongitudinalPattern.GRADUAL_DECLINE:
            return 0.2 + (0.6 * progress)  # Linear increase
        
        elif pattern == LongitudinalPattern.ACUTE_CRISIS:
            if progress > 0.8:
                return 0.9  # Sudden spike at end
            return 0.2 + (0.1 * (session_idx % 4) / 4)
        
        elif pattern == LongitudinalPattern.CYCLICAL:
            import math
            return 0.3 + 0.3 * math.sin(progress * 4 * math.pi)  # Oscillating
        
        elif pattern == LongitudinalPattern.RECOVERY:
            return 0.7 - (0.5 * progress)  # Decreasing
        
        elif pattern == LongitudinalPattern.SEASONAL:
            # Higher in winter months (simulated)
            return 0.3 + (0.3 if session_idx % 4 < 2 else 0.0)
        
        return 0.3  # Default
    
    def analyze_history(self, history: StudentHistory) -> PatternPrediction:
        """Analyze student history to predict pattern.
        
        Args:
            history: Student's historical data
            
        Returns:
            PatternPrediction with analysis
        """
        # Calculate trend
        if len(history.risk_trajectory) < 2:
            predicted_pattern = LongitudinalPattern.STABLE_HEALTHY
            confidence = 0.5
        else:
            trajectory = history.risk_trajectory
            
            # Calculate slope
            n = len(trajectory)
            x_mean = (n - 1) / 2
            y_mean = sum(trajectory) / n
            
            numerator = sum((i - x_mean) * (trajectory[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            
            slope = numerator / denominator if denominator != 0 else 0
            
            # Calculate variance for cyclical detection
            variance = statistics.variance(trajectory) if len(trajectory) > 1 else 0
            
            # Classify pattern
            avg_risk = history.avg_risk_score
            
            if slope > 0.02:
                if history.crisis_count > 0 and trajectory[-1] > 0.8:
                    predicted_pattern = LongitudinalPattern.ACUTE_CRISIS
                else:
                    predicted_pattern = LongitudinalPattern.GRADUAL_DECLINE
                confidence = min(0.9, 0.5 + abs(slope) * 5)
                
            elif slope < -0.02:
                predicted_pattern = LongitudinalPattern.RECOVERY
                confidence = min(0.9, 0.5 + abs(slope) * 5)
                
            elif variance > 0.04:
                predicted_pattern = LongitudinalPattern.CYCLICAL
                confidence = min(0.85, 0.5 + variance * 5)
                
            elif avg_risk < 0.25:
                predicted_pattern = LongitudinalPattern.STABLE_HEALTHY
                confidence = 0.8
                
            elif avg_risk < 0.45:
                predicted_pattern = LongitudinalPattern.CHRONIC_LOW
                confidence = 0.7
                
            else:
                predicted_pattern = LongitudinalPattern.GRADUAL_DECLINE
                confidence = 0.6
        
        # Calculate early warning score
        early_warning = self._calculate_early_warning(history)
        
        # Generate risk factors
        risk_factors = self._identify_risk_factors(history)
        
        # Recommend intervention
        intervention = self._recommend_intervention(predicted_pattern, early_warning)
        
        return PatternPrediction(
            student_id_hash=history.student_id_hash,
            predicted_pattern=predicted_pattern,
            confidence=confidence,
            risk_factors=risk_factors,
            recommended_intervention=intervention,
            early_warning_score=early_warning,
            supporting_evidence=[
                f"Analyzed {history.session_count} sessions over {history.duration_days} days",
                f"Average risk score: {history.avg_risk_score:.2f}",
                f"Crisis events: {history.crisis_count}",
            ],
        )
    
    def _calculate_early_warning(self, history: StudentHistory) -> float:
        """Calculate early warning score for future escalation.
        
        Args:
            history: Student history
            
        Returns:
            Score between 0 and 1
        """
        score = 0.0
        
        # Recent trend (last 5 sessions)
        if len(history.risk_trajectory) >= 5:
            recent = history.risk_trajectory[-5:]
            recent_avg = sum(recent) / len(recent)
            overall_avg = history.avg_risk_score
            
            if recent_avg > overall_avg + 0.1:
                score += 0.3  # Recent worsening
        
        # Crisis history
        if history.crisis_count > 0:
            score += min(0.3, history.crisis_count * 0.1)
        
        # High average risk
        if history.avg_risk_score > 0.5:
            score += 0.2
        
        # Accelerating trend
        if len(history.risk_trajectory) >= 3:
            recent_slope = (
                history.risk_trajectory[-1] - history.risk_trajectory[-3]
            ) / 2
            if recent_slope > 0.1:
                score += 0.2
        
        return min(1.0, score)
    
    def _identify_risk_factors(self, history: StudentHistory) -> List[str]:
        """Identify risk factors from history.
        
        Args:
            history: Student history
            
        Returns:
            List of identified risk factors
        """
        factors = []
        
        if history.crisis_count > 0:
            factors.append(f"Prior crisis events ({history.crisis_count})")
        
        if history.avg_risk_score > 0.5:
            factors.append("Elevated average risk score")
        
        if len(history.risk_trajectory) >= 5:
            recent = history.risk_trajectory[-5:]
            if all(r > 0.4 for r in recent):
                factors.append("Sustained elevated risk in recent sessions")
        
        if history.duration_days > 30 and history.session_count < 3:
            factors.append("Infrequent engagement despite extended period")
        
        return factors
    
    def _recommend_intervention(
        self,
        pattern: LongitudinalPattern,
        early_warning: float,
    ) -> str:
        """Recommend intervention based on pattern and risk.
        
        Args:
            pattern: Detected pattern
            early_warning: Early warning score
            
        Returns:
            Intervention recommendation
        """
        if early_warning > 0.7:
            return "URGENT: Schedule immediate counselor check-in"
        
        if pattern == LongitudinalPattern.GRADUAL_DECLINE:
            return "Schedule proactive counselor outreach within 48 hours"
        
        if pattern == LongitudinalPattern.ACUTE_CRISIS:
            return "URGENT: Immediate crisis protocol activation"
        
        if pattern == LongitudinalPattern.CHRONIC_LOW:
            return "Consider referral to ongoing support group"
        
        if pattern == LongitudinalPattern.CYCLICAL:
            return "Identify triggers; schedule check-ins during high-risk periods"
        
        if pattern == LongitudinalPattern.RECOVERY:
            return "Continue current support; monitor for relapse"
        
        return "Continue standard monitoring"
    
    def evaluate_pattern_detection(
        self,
        num_samples_per_pattern: int = 10,
    ) -> LongitudinalTriageResult:
        """Evaluate pattern detection across all pattern types.
        
        Args:
            num_samples_per_pattern: Samples to generate per pattern
            
        Returns:
            LongitudinalTriageResult with metrics
        """
        run_id = f"long_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()
        
        logger.info(
            "LONGITUDINAL_TRIAGE_EVALUATION_STARTED",
            extra={"run_id": run_id, "samples_per_pattern": num_samples_per_pattern}
        )
        
        metrics = LongitudinalMetrics()
        predictions = []
        missed_patterns = []
        false_alarms = []
        
        # Test each pattern type
        for pattern in LongitudinalPattern:
            for i in range(num_samples_per_pattern):
                # Generate synthetic history
                history = self.generate_synthetic_history(
                    pattern=pattern,
                    duration_days=30 + (i * 7),  # Varying durations
                )
                
                # Analyze and predict
                prediction = self.analyze_history(history)
                predictions.append(prediction)
                
                metrics.total_students += 1
                metrics.patterns_expected += 1
                
                # Check if pattern was correctly identified
                if prediction.predicted_pattern == pattern:
                    metrics.patterns_correct += 1
                else:
                    missed_patterns.append(history.student_id_hash)
                
                # Track early warning accuracy for escalating patterns
                is_escalating = pattern in [
                    LongitudinalPattern.GRADUAL_DECLINE,
                    LongitudinalPattern.ACUTE_CRISIS,
                ]
                predicted_escalation = prediction.early_warning_score > 0.5
                
                if is_escalating:
                    metrics.escalations_actual += 1
                    if predicted_escalation:
                        metrics.true_positives += 1
                        metrics.escalations_predicted += 1
                    else:
                        metrics.false_negatives += 1
                else:
                    if predicted_escalation:
                        metrics.false_positives += 1
                        metrics.escalations_predicted += 1
                        false_alarms.append(history.student_id_hash)
        
        completed_at = datetime.utcnow()
        
        logger.info(
            "LONGITUDINAL_TRIAGE_EVALUATION_COMPLETED",
            extra={
                "run_id": run_id,
                "total_students": metrics.total_students,
                "pattern_accuracy": metrics.pattern_accuracy,
                "early_warning_recall": metrics.early_warning_recall,
            }
        )
        
        return LongitudinalTriageResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            metrics=metrics,
            predictions=predictions,
            missed_patterns=missed_patterns,
            false_alarms=false_alarms,
        )
