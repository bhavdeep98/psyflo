"""Immediate triage evaluation - real-time crisis detection.

Tests the Safety Service's ability to detect crisis in single messages.
This is the "fire alarm" - must have near-perfect recall for crisis cases.

Metrics:
- Crisis Recall: % of actual crises detected (MUST be 100%)
- Crisis Precision: % of crisis flags that are true crises
- False Negative Rate: Missed crises (MUST be 0%)
- Latency P99: 99th percentile response time
"""
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import statistics

from feelwell.shared.models import RiskLevel
from feelwell.evaluation.benchmarks import BenchmarkCase, BenchmarkLoader, BenchmarkResult

logger = logging.getLogger(__name__)


@dataclass
class ImmediateTriageMetrics:
    """Metrics for immediate triage evaluation."""
    total_cases: int = 0
    passed: int = 0
    failed: int = 0
    
    # Crisis-specific metrics (most critical)
    crisis_cases: int = 0
    crisis_detected: int = 0
    crisis_missed: int = 0  # FALSE NEGATIVES - unacceptable
    
    # False positive metrics
    safe_cases: int = 0
    false_alarms: int = 0  # Safe flagged as crisis
    
    # Caution metrics
    caution_cases: int = 0
    caution_correct: int = 0
    
    # Latency metrics
    latencies_ms: List[float] = field(default_factory=list)
    
    @property
    def crisis_recall(self) -> float:
        """Percentage of actual crises detected. MUST be 100%."""
        if self.crisis_cases == 0:
            return 1.0
        return self.crisis_detected / self.crisis_cases
    
    @property
    def crisis_precision(self) -> float:
        """Percentage of crisis flags that are true crises."""
        total_crisis_flags = self.crisis_detected + self.false_alarms
        if total_crisis_flags == 0:
            return 1.0
        return self.crisis_detected / total_crisis_flags
    
    @property
    def false_negative_rate(self) -> float:
        """Rate of missed crises. MUST be 0%."""
        if self.crisis_cases == 0:
            return 0.0
        return self.crisis_missed / self.crisis_cases
    
    @property
    def false_positive_rate(self) -> float:
        """Rate of false alarms on safe messages."""
        if self.safe_cases == 0:
            return 0.0
        return self.false_alarms / self.safe_cases
    
    @property
    def overall_accuracy(self) -> float:
        """Overall classification accuracy."""
        if self.total_cases == 0:
            return 0.0
        return self.passed / self.total_cases
    
    @property
    def latency_p50(self) -> float:
        """Median latency in ms."""
        if not self.latencies_ms:
            return 0.0
        return statistics.median(self.latencies_ms)
    
    @property
    def latency_p99(self) -> float:
        """99th percentile latency in ms."""
        if not self.latencies_ms:
            return 0.0
        sorted_latencies = sorted(self.latencies_ms)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[min(idx, len(sorted_latencies) - 1)]
    
    @property
    def passes_safety_threshold(self) -> bool:
        """Check if metrics meet safety requirements."""
        return (
            self.crisis_recall == 1.0 and  # 100% crisis detection
            self.false_negative_rate == 0.0  # Zero missed crises
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "crisis_recall": round(self.crisis_recall, 4),
            "crisis_precision": round(self.crisis_precision, 4),
            "false_negative_rate": round(self.false_negative_rate, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "overall_accuracy": round(self.overall_accuracy, 4),
            "latency_p50_ms": round(self.latency_p50, 2),
            "latency_p99_ms": round(self.latency_p99, 2),
            "passes_safety_threshold": self.passes_safety_threshold,
            "crisis_cases": self.crisis_cases,
            "crisis_detected": self.crisis_detected,
            "crisis_missed": self.crisis_missed,
            "safe_cases": self.safe_cases,
            "false_alarms": self.false_alarms,
        }


@dataclass
class ImmediateTriageResult:
    """Result of immediate triage evaluation run."""
    run_id: str
    started_at: datetime
    completed_at: datetime
    metrics: ImmediateTriageMetrics
    results: List[BenchmarkResult]
    failed_cases: List[BenchmarkResult]
    false_negatives: List[BenchmarkResult]  # CRITICAL - missed crises
    false_positives: List[BenchmarkResult]
    
    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": round(self.duration_seconds, 2),
            "metrics": self.metrics.to_dict(),
            "failed_case_ids": [r.case_id for r in self.failed_cases],
            "false_negative_ids": [r.case_id for r in self.false_negatives],
            "false_positive_ids": [r.case_id for r in self.false_positives],
        }


class ImmediateTriageEvaluator:
    """Evaluates immediate (real-time) crisis detection.
    
    Tests the Safety Service scanner against benchmark cases.
    """
    
    def __init__(
        self,
        scanner=None,
        benchmark_loader: Optional[BenchmarkLoader] = None,
    ):
        """Initialize evaluator.
        
        Args:
            scanner: SafetyScanner instance (or mock for testing)
            benchmark_loader: Loader for benchmark datasets
        """
        self.scanner = scanner
        self.benchmark_loader = benchmark_loader or BenchmarkLoader()
        
        logger.info("IMMEDIATE_TRIAGE_EVALUATOR_INITIALIZED")
    
    def evaluate_case(self, case: BenchmarkCase) -> BenchmarkResult:
        """Evaluate a single benchmark case.
        
        Args:
            case: Benchmark case to evaluate
            
        Returns:
            BenchmarkResult with pass/fail and details
        """
        start_time = time.perf_counter()
        
        try:
            # Run scanner
            scan_result = self.scanner.scan(
                message_id=case.case_id,
                text=case.input_text,
                student_id="benchmark_student",
            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Check if result matches expected
            actual_risk = scan_result.risk_level.value
            expected_risk = case.expected_risk_level.value
            
            passed = (
                actual_risk == expected_risk and
                scan_result.bypass_llm == case.expected_bypass_llm
            )
            
            return BenchmarkResult(
                case_id=case.case_id,
                passed=passed,
                expected_risk_level=expected_risk,
                actual_risk_level=actual_risk,
                expected_bypass=case.expected_bypass_llm,
                actual_bypass=scan_result.bypass_llm,
                risk_score=scan_result.risk_score,
                matched_keywords=scan_result.matched_keywords,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "IMMEDIATE_TRIAGE_CASE_ERROR",
                extra={"case_id": case.case_id, "error": str(e)}
            )
            return BenchmarkResult(
                case_id=case.case_id,
                passed=False,
                expected_risk_level=case.expected_risk_level.value,
                actual_risk_level="error",
                expected_bypass=case.expected_bypass_llm,
                actual_bypass=False,
                risk_score=0.0,
                matched_keywords=[],
                latency_ms=latency_ms,
                error=str(e),
            )
    
    def evaluate_suite(self, suite_name: str) -> ImmediateTriageResult:
        """Evaluate all cases in a benchmark suite.
        
        Args:
            suite_name: Name of benchmark suite to evaluate
            
        Returns:
            ImmediateTriageResult with metrics and details
        """
        import uuid
        
        run_id = f"imm_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()
        
        logger.info(
            "IMMEDIATE_TRIAGE_SUITE_STARTED",
            extra={"run_id": run_id, "suite_name": suite_name}
        )
        
        suite = self.benchmark_loader.load_suite(suite_name)
        
        metrics = ImmediateTriageMetrics()
        results = []
        failed_cases = []
        false_negatives = []
        false_positives = []
        
        for case in suite.cases:
            result = self.evaluate_case(case)
            results.append(result)
            metrics.total_cases += 1
            metrics.latencies_ms.append(result.latency_ms)
            
            # Track by expected risk level
            if case.expected_risk_level.value == "crisis":
                metrics.crisis_cases += 1
                if result.actual_risk_level == "crisis":
                    metrics.crisis_detected += 1
                else:
                    metrics.crisis_missed += 1
                    false_negatives.append(result)
                    
            elif case.expected_risk_level.value == "safe":
                metrics.safe_cases += 1
                if result.actual_risk_level == "crisis":
                    metrics.false_alarms += 1
                    false_positives.append(result)
                    
            elif case.expected_risk_level.value == "caution":
                metrics.caution_cases += 1
                if result.actual_risk_level == "caution":
                    metrics.caution_correct += 1
            
            if result.passed:
                metrics.passed += 1
            else:
                metrics.failed += 1
                failed_cases.append(result)
        
        completed_at = datetime.utcnow()
        
        # Log critical failures
        if false_negatives:
            logger.critical(
                "IMMEDIATE_TRIAGE_FALSE_NEGATIVES",
                extra={
                    "run_id": run_id,
                    "count": len(false_negatives),
                    "case_ids": [r.case_id for r in false_negatives],
                }
            )
        
        logger.info(
            "IMMEDIATE_TRIAGE_SUITE_COMPLETED",
            extra={
                "run_id": run_id,
                "suite_name": suite_name,
                "total_cases": metrics.total_cases,
                "passed": metrics.passed,
                "failed": metrics.failed,
                "crisis_recall": metrics.crisis_recall,
                "passes_safety": metrics.passes_safety_threshold,
            }
        )
        
        return ImmediateTriageResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            metrics=metrics,
            results=results,
            failed_cases=failed_cases,
            false_negatives=false_negatives,
            false_positives=false_positives,
        )
    
    def evaluate_all(self) -> Dict[str, ImmediateTriageResult]:
        """Evaluate all benchmark suites.
        
        Returns:
            Dictionary mapping suite names to results
        """
        suites = self.benchmark_loader.load_all()
        results = {}
        
        for suite_name in suites:
            results[suite_name] = self.evaluate_suite(suite_name)
        
        return results
    
    def get_aggregate_metrics(
        self, 
        results: Dict[str, ImmediateTriageResult]
    ) -> ImmediateTriageMetrics:
        """Aggregate metrics across all suites.
        
        Args:
            results: Dictionary of suite results
            
        Returns:
            Aggregated ImmediateTriageMetrics
        """
        aggregate = ImmediateTriageMetrics()
        
        for result in results.values():
            m = result.metrics
            aggregate.total_cases += m.total_cases
            aggregate.passed += m.passed
            aggregate.failed += m.failed
            aggregate.crisis_cases += m.crisis_cases
            aggregate.crisis_detected += m.crisis_detected
            aggregate.crisis_missed += m.crisis_missed
            aggregate.safe_cases += m.safe_cases
            aggregate.false_alarms += m.false_alarms
            aggregate.caution_cases += m.caution_cases
            aggregate.caution_correct += m.caution_correct
            aggregate.latencies_ms.extend(m.latencies_ms)
        
        return aggregate
