"""Session-level triage evaluation - mid-term risk trajectory.

Tests the Observer Service's ability to track risk across a conversation.
Evaluates clinical marker detection, PHQ-9/GAD-7 scoring, and trajectory analysis.

Metrics:
- Trajectory Accuracy: Correct identification of escalating/stable/improving
- PHQ-9 Correlation: Correlation between predicted and expected scores
- Marker Detection Rate: % of expected clinical markers detected
- Escalation Detection: % of escalating sessions correctly flagged
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import statistics
import uuid

from feelwell.shared.models import RiskLevel
from feelwell.evaluation.benchmarks import BenchmarkCase, BenchmarkLoader

logger = logging.getLogger(__name__)


class RiskTrajectory:
    """Risk trajectory classifications."""
    ESCALATING = "escalating"
    STABLE = "stable"
    IMPROVING = "improving"
    CRISIS = "crisis"  # Immediate crisis detected


@dataclass
class SessionSnapshot:
    """Snapshot of session state at a point in time."""
    message_index: int
    message_text: str
    risk_score: float
    risk_level: str
    markers_detected: List[str]
    phq9_contribution: int
    gad7_contribution: int
    timestamp: datetime


@dataclass
class SessionAnalysis:
    """Complete analysis of a session."""
    session_id: str
    snapshots: List[SessionSnapshot]
    trajectory: str
    final_risk_level: str
    final_risk_score: float
    total_phq9_score: int
    total_gad7_score: int
    counselor_flag: bool
    crisis_triggered: bool
    
    @property
    def message_count(self) -> int:
        return len(self.snapshots)
    
    @property
    def risk_delta(self) -> float:
        """Change in risk from start to end."""
        if len(self.snapshots) < 2:
            return 0.0
        return self.snapshots[-1].risk_score - self.snapshots[0].risk_score


@dataclass
class SessionTriageMetrics:
    """Metrics for session-level triage evaluation."""
    total_sessions: int = 0
    
    # Trajectory metrics
    trajectory_correct: int = 0
    escalating_detected: int = 0
    escalating_missed: int = 0
    
    # Clinical score metrics
    phq9_scores: List[Tuple[int, int]] = field(default_factory=list)  # (expected, actual)
    gad7_scores: List[Tuple[int, int]] = field(default_factory=list)
    
    # Marker detection
    markers_expected: int = 0
    markers_detected: int = 0
    
    # Counselor flagging
    should_flag: int = 0
    correctly_flagged: int = 0
    
    @property
    def trajectory_accuracy(self) -> float:
        if self.total_sessions == 0:
            return 0.0
        return self.trajectory_correct / self.total_sessions
    
    @property
    def escalation_recall(self) -> float:
        """% of escalating sessions detected."""
        total_escalating = self.escalating_detected + self.escalating_missed
        if total_escalating == 0:
            return 1.0
        return self.escalating_detected / total_escalating
    
    @property
    def marker_detection_rate(self) -> float:
        if self.markers_expected == 0:
            return 1.0
        return self.markers_detected / self.markers_expected
    
    @property
    def phq9_mae(self) -> float:
        """Mean Absolute Error for PHQ-9 scores."""
        if not self.phq9_scores:
            return 0.0
        errors = [abs(exp - act) for exp, act in self.phq9_scores]
        return statistics.mean(errors)
    
    @property
    def counselor_flag_accuracy(self) -> float:
        if self.should_flag == 0:
            return 1.0
        return self.correctly_flagged / self.should_flag
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "trajectory_accuracy": round(self.trajectory_accuracy, 4),
            "escalation_recall": round(self.escalation_recall, 4),
            "marker_detection_rate": round(self.marker_detection_rate, 4),
            "phq9_mae": round(self.phq9_mae, 2),
            "counselor_flag_accuracy": round(self.counselor_flag_accuracy, 4),
        }


@dataclass
class SessionTriageResult:
    """Result of session triage evaluation."""
    run_id: str
    started_at: datetime
    completed_at: datetime
    metrics: SessionTriageMetrics
    session_analyses: List[SessionAnalysis]
    failed_sessions: List[str]
    missed_escalations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "metrics": self.metrics.to_dict(),
            "failed_session_ids": self.failed_sessions,
            "missed_escalation_ids": self.missed_escalations,
        }


class SessionTriageEvaluator:
    """Evaluates session-level (mid-term) risk trajectory.
    
    Tests the Observer Service's ability to:
    1. Track risk across multiple messages
    2. Detect clinical markers (PHQ-9, GAD-7)
    3. Identify escalating vs stable vs improving trajectories
    4. Flag sessions for counselor review
    """
    
    def __init__(
        self,
        analyzer=None,
        marker_detector=None,
        benchmark_loader: Optional[BenchmarkLoader] = None,
    ):
        """Initialize evaluator.
        
        Args:
            analyzer: MessageAnalyzer instance
            marker_detector: ClinicalMarkerDetector instance
            benchmark_loader: Loader for benchmark datasets
        """
        self.analyzer = analyzer
        self.marker_detector = marker_detector
        self.benchmark_loader = benchmark_loader or BenchmarkLoader()
        
        logger.info("SESSION_TRIAGE_EVALUATOR_INITIALIZED")
    
    def analyze_session(
        self,
        session_id: str,
        messages: List[str],
        student_id: str = "benchmark_student",
    ) -> SessionAnalysis:
        """Analyze a complete session.
        
        Args:
            session_id: Session identifier
            messages: List of messages in chronological order
            student_id: Student identifier
            
        Returns:
            SessionAnalysis with trajectory and scores
        """
        snapshots = []
        cumulative_phq9 = 0
        cumulative_gad7 = 0
        crisis_triggered = False
        
        base_time = datetime.utcnow()
        
        for idx, message in enumerate(messages):
            message_id = f"{session_id}_msg_{idx}"
            
            # Analyze message
            if self.analyzer:
                snapshot_result = self.analyzer.analyze(
                    message_id=message_id,
                    session_id=session_id,
                    student_id=student_id,
                    text=message,
                    safety_risk_score=0.0,  # Assume safety already passed
                )
                
                risk_score = snapshot_result.risk_score
                risk_level = snapshot_result.risk_level.value
                markers = [m.item_id for m in snapshot_result.markers]
                
                # Calculate clinical scores from markers
                if self.marker_detector:
                    phq9_contrib = self.marker_detector.calculate_phq9_score(
                        snapshot_result.markers
                    ) or 0
                    gad7_contrib = self.marker_detector.calculate_gad7_score(
                        snapshot_result.markers
                    ) or 0
                else:
                    phq9_contrib = 0
                    gad7_contrib = 0
            else:
                # Mock analysis for testing without real services
                risk_score = 0.3 + (idx * 0.1)  # Simulated escalation
                risk_level = "caution" if risk_score > 0.4 else "safe"
                markers = []
                phq9_contrib = 0
                gad7_contrib = 0
            
            cumulative_phq9 += phq9_contrib
            cumulative_gad7 += gad7_contrib
            
            if risk_level == "crisis":
                crisis_triggered = True
            
            snapshot = SessionSnapshot(
                message_index=idx,
                message_text=message[:100],  # Truncate for storage
                risk_score=risk_score,
                risk_level=risk_level,
                markers_detected=markers,
                phq9_contribution=phq9_contrib,
                gad7_contribution=gad7_contrib,
                timestamp=base_time + timedelta(minutes=idx * 2),
            )
            snapshots.append(snapshot)
        
        # Determine trajectory
        trajectory = self._calculate_trajectory(snapshots)
        
        # Determine if counselor should be flagged
        counselor_flag = (
            crisis_triggered or
            cumulative_phq9 >= 10 or
            cumulative_gad7 >= 10 or
            trajectory == RiskTrajectory.ESCALATING
        )
        
        return SessionAnalysis(
            session_id=session_id,
            snapshots=snapshots,
            trajectory=trajectory,
            final_risk_level=snapshots[-1].risk_level if snapshots else "safe",
            final_risk_score=snapshots[-1].risk_score if snapshots else 0.0,
            total_phq9_score=cumulative_phq9,
            total_gad7_score=cumulative_gad7,
            counselor_flag=counselor_flag,
            crisis_triggered=crisis_triggered,
        )
    
    def _calculate_trajectory(self, snapshots: List[SessionSnapshot]) -> str:
        """Calculate risk trajectory from snapshots.
        
        Args:
            snapshots: List of session snapshots
            
        Returns:
            Trajectory classification
        """
        if not snapshots:
            return RiskTrajectory.STABLE
        
        if len(snapshots) < 2:
            return RiskTrajectory.STABLE
        
        # Check for crisis
        if any(s.risk_level == "crisis" for s in snapshots):
            return RiskTrajectory.CRISIS
        
        # Calculate trend
        risk_scores = [s.risk_score for s in snapshots]
        
        # Simple linear trend
        n = len(risk_scores)
        if n < 2:
            return RiskTrajectory.STABLE
        
        # Calculate slope using least squares
        x_mean = (n - 1) / 2
        y_mean = sum(risk_scores) / n
        
        numerator = sum((i - x_mean) * (risk_scores[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return RiskTrajectory.STABLE
        
        slope = numerator / denominator
        
        # Classify based on slope
        if slope > 0.05:
            return RiskTrajectory.ESCALATING
        elif slope < -0.05:
            return RiskTrajectory.IMPROVING
        else:
            return RiskTrajectory.STABLE
    
    def evaluate_case(self, case: BenchmarkCase) -> Tuple[SessionAnalysis, bool]:
        """Evaluate a session progression benchmark case.
        
        Args:
            case: Benchmark case with session_context
            
        Returns:
            Tuple of (SessionAnalysis, passed)
        """
        # Build message list from context + final message
        messages = list(case.session_context or [])
        messages.append(case.input_text)
        
        analysis = self.analyze_session(
            session_id=case.case_id,
            messages=messages,
        )
        
        # Check if analysis matches expectations
        passed = True
        
        # Check risk level
        if analysis.final_risk_level != case.expected_risk_level.value:
            passed = False
        
        # Check PHQ-9 range if specified
        if case.expected_phq9_range:
            min_phq9, max_phq9 = case.expected_phq9_range
            if not (min_phq9 <= analysis.total_phq9_score <= max_phq9):
                passed = False
        
        # Check markers if specified
        if case.expected_markers:
            detected_markers = set()
            for snapshot in analysis.snapshots:
                detected_markers.update(snapshot.markers_detected)
            
            for expected_marker in case.expected_markers:
                if expected_marker not in detected_markers:
                    passed = False
                    break
        
        return analysis, passed
    
    def evaluate_suite(self, suite_name: str = "session_progression") -> SessionTriageResult:
        """Evaluate session progression benchmark suite.
        
        Args:
            suite_name: Name of benchmark suite
            
        Returns:
            SessionTriageResult with metrics
        """
        run_id = f"sess_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()
        
        logger.info(
            "SESSION_TRIAGE_SUITE_STARTED",
            extra={"run_id": run_id, "suite_name": suite_name}
        )
        
        suite = self.benchmark_loader.load_suite(suite_name)
        
        metrics = SessionTriageMetrics()
        analyses = []
        failed_sessions = []
        missed_escalations = []
        
        for case in suite.cases:
            if case.session_context is None:
                continue  # Skip non-session cases
            
            analysis, passed = self.evaluate_case(case)
            analyses.append(analysis)
            metrics.total_sessions += 1
            
            if passed:
                metrics.trajectory_correct += 1
            else:
                failed_sessions.append(case.case_id)
            
            # Track escalation detection
            expected_escalating = case.expected_risk_level.value == "crisis"
            actual_escalating = analysis.trajectory in [
                RiskTrajectory.ESCALATING, 
                RiskTrajectory.CRISIS
            ]
            
            if expected_escalating:
                if actual_escalating:
                    metrics.escalating_detected += 1
                else:
                    metrics.escalating_missed += 1
                    missed_escalations.append(case.case_id)
            
            # Track PHQ-9 scores
            if case.expected_phq9_range:
                expected_mid = sum(case.expected_phq9_range) // 2
                metrics.phq9_scores.append((expected_mid, analysis.total_phq9_score))
            
            # Track marker detection
            if case.expected_markers:
                metrics.markers_expected += len(case.expected_markers)
                detected = set()
                for snapshot in analysis.snapshots:
                    detected.update(snapshot.markers_detected)
                for marker in case.expected_markers:
                    if marker in detected:
                        metrics.markers_detected += 1
            
            # Track counselor flagging
            if case.expected_risk_level.value in ["crisis", "caution"]:
                metrics.should_flag += 1
                if analysis.counselor_flag:
                    metrics.correctly_flagged += 1
        
        completed_at = datetime.utcnow()
        
        logger.info(
            "SESSION_TRIAGE_SUITE_COMPLETED",
            extra={
                "run_id": run_id,
                "total_sessions": metrics.total_sessions,
                "trajectory_accuracy": metrics.trajectory_accuracy,
                "escalation_recall": metrics.escalation_recall,
            }
        )
        
        return SessionTriageResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            metrics=metrics,
            session_analyses=analyses,
            failed_sessions=failed_sessions,
            missed_escalations=missed_escalations,
        )
