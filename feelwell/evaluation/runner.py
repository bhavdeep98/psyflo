"""Main evaluation runner - orchestrates all evaluation components.

Runs comprehensive evaluation against:
1. Internal benchmarks (crisis detection, false positives, etc.)
2. External datasets (MentalChat16K, PHQ-9, Clinical Decisions)
3. Multi-tier triage (immediate, session, longitudinal)
4. Test suites (E2E, Integration, Canary)

Generates detailed reports with metrics for:
- Safety (crisis recall, false negative rate)
- Accuracy (precision, recall, F1 by category)
- Latency (P50, P99)
- Clinical alignment (PHQ-9 correlation, decision accuracy)
"""
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """Configuration for evaluation run."""
    # What to evaluate
    run_internal_benchmarks: bool = True
    run_external_datasets: bool = True
    run_triage_evaluation: bool = True
    run_test_suites: bool = True
    
    # Dataset options
    max_samples_per_dataset: Optional[int] = None
    datasets_to_include: List[str] = field(default_factory=lambda: [
        "mentalchat16k", "phq9_depression", "clinical_decisions"
    ])
    
    # Output options
    output_dir: Path = field(default_factory=lambda: Path("feelwell/evaluation/results"))
    save_detailed_results: bool = True
    generate_report: bool = True
    
    def __post_init__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class CategoryMetrics:
    """Metrics for a specific category."""
    category: str
    total: int = 0
    correct: int = 0
    crisis_true_positives: int = 0
    crisis_false_positives: int = 0
    crisis_false_negatives: int = 0
    
    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total > 0 else 0.0
    
    @property
    def crisis_precision(self) -> float:
        denom = self.crisis_true_positives + self.crisis_false_positives
        return self.crisis_true_positives / denom if denom > 0 else 0.0
    
    @property
    def crisis_recall(self) -> float:
        denom = self.crisis_true_positives + self.crisis_false_negatives
        return self.crisis_true_positives / denom if denom > 0 else 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "total": self.total,
            "accuracy": round(self.accuracy, 4),
            "crisis_precision": round(self.crisis_precision, 4),
            "crisis_recall": round(self.crisis_recall, 4),
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result."""
    run_id: str
    started_at: datetime
    completed_at: datetime
    config: EvaluationConfig
    
    # Aggregate metrics
    total_samples_evaluated: int = 0
    overall_accuracy: float = 0.0
    crisis_recall: float = 0.0  # MUST be 100%
    crisis_precision: float = 0.0
    false_negative_count: int = 0  # MUST be 0
    
    # Category breakdown
    metrics_by_category: Dict[str, CategoryMetrics] = field(default_factory=dict)
    metrics_by_dataset: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Triage metrics
    immediate_triage_metrics: Optional[Dict[str, Any]] = None
    session_triage_metrics: Optional[Dict[str, Any]] = None
    longitudinal_triage_metrics: Optional[Dict[str, Any]] = None
    
    # Test suite results
    e2e_results: Optional[Dict[str, Any]] = None
    integration_results: Optional[Dict[str, Any]] = None
    canary_results: Optional[Dict[str, Any]] = None
    
    # Latency
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # Safety assessment
    passes_safety_threshold: bool = False
    safety_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": (self.completed_at - self.started_at).total_seconds(),
            "total_samples_evaluated": self.total_samples_evaluated,
            "overall_accuracy": round(self.overall_accuracy, 4),
            "crisis_recall": round(self.crisis_recall, 4),
            "crisis_precision": round(self.crisis_precision, 4),
            "false_negative_count": self.false_negative_count,
            "passes_safety_threshold": self.passes_safety_threshold,
            "safety_issues": self.safety_issues,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "metrics_by_category": {
                k: v.to_dict() for k, v in self.metrics_by_category.items()
            },
            "metrics_by_dataset": self.metrics_by_dataset,
            "e2e_results": self.e2e_results,
            "integration_results": self.integration_results,
            "canary_results": self.canary_results,
        }


class EvaluationRunner:
    """Main evaluation runner."""
    
    def __init__(
        self,
        config: Optional[EvaluationConfig] = None,
        scanner=None,
        analyzer=None,
    ):
        """Initialize runner.
        
        Args:
            config: Evaluation configuration
            scanner: SafetyScanner instance
            analyzer: MessageAnalyzer instance
        """
        self.config = config or EvaluationConfig()
        self.scanner = scanner
        self.analyzer = analyzer
        
        # Initialize components lazily
        self._benchmark_loader = None
        self._dataset_loaders = {}
        self._triage_evaluators = {}
        self._test_suites = {}
        
        logger.info(
            "EVALUATION_RUNNER_INITIALIZED",
            extra={"config": str(self.config)}
        )
    
    def run(self) -> EvaluationResult:
        """Run complete evaluation.
        
        Returns:
            EvaluationResult with all metrics
        """
        run_id = f"eval_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()
        
        logger.info("EVALUATION_STARTED", extra={"run_id": run_id})
        
        result = EvaluationResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=started_at,
            config=self.config,
        )
        
        all_latencies = []
        total_correct = 0
        total_samples = 0
        crisis_tp = 0
        crisis_fp = 0
        crisis_fn = 0
        
        try:
            # 1. Internal benchmarks
            if self.config.run_internal_benchmarks:
                benchmark_results = self._run_internal_benchmarks()
                for name, metrics in benchmark_results.items():
                    result.metrics_by_dataset[f"benchmark_{name}"] = metrics
                    total_samples += metrics.get("total", 0)
                    total_correct += metrics.get("correct", 0)
                    crisis_tp += metrics.get("crisis_tp", 0)
                    crisis_fp += metrics.get("crisis_fp", 0)
                    crisis_fn += metrics.get("crisis_fn", 0)
                    all_latencies.extend(metrics.get("latencies", []))
            
            # 2. External datasets
            if self.config.run_external_datasets:
                dataset_results = self._run_external_datasets()
                for name, metrics in dataset_results.items():
                    result.metrics_by_dataset[name] = metrics
                    result.metrics_by_category[metrics.get("category", "unknown")] = \
                        CategoryMetrics(
                            category=metrics.get("category", "unknown"),
                            total=metrics.get("total", 0),
                            correct=metrics.get("correct", 0),
                        )
                    total_samples += metrics.get("total", 0)
                    total_correct += metrics.get("correct", 0)
            
            # 3. Triage evaluation
            if self.config.run_triage_evaluation:
                triage_results = self._run_triage_evaluation()
                result.immediate_triage_metrics = triage_results.get("immediate")
                result.session_triage_metrics = triage_results.get("session")
                result.longitudinal_triage_metrics = triage_results.get("longitudinal")
            
            # 4. Test suites
            if self.config.run_test_suites:
                suite_results = self._run_test_suites()
                result.e2e_results = suite_results.get("e2e")
                result.integration_results = suite_results.get("integration")
                result.canary_results = suite_results.get("canary")
            
            # Calculate aggregate metrics
            result.total_samples_evaluated = total_samples
            result.overall_accuracy = total_correct / total_samples if total_samples > 0 else 0.0
            
            # Crisis metrics
            result.crisis_recall = crisis_tp / (crisis_tp + crisis_fn) if (crisis_tp + crisis_fn) > 0 else 1.0
            result.crisis_precision = crisis_tp / (crisis_tp + crisis_fp) if (crisis_tp + crisis_fp) > 0 else 1.0
            result.false_negative_count = crisis_fn
            
            # Latency metrics
            if all_latencies:
                all_latencies.sort()
                result.avg_latency_ms = sum(all_latencies) / len(all_latencies)
                p99_idx = int(len(all_latencies) * 0.99)
                result.p99_latency_ms = all_latencies[min(p99_idx, len(all_latencies) - 1)]
            
            # Safety assessment
            result.passes_safety_threshold = (
                result.crisis_recall == 1.0 and
                result.false_negative_count == 0
            )
            
            if result.crisis_recall < 1.0:
                result.safety_issues.append(
                    f"Crisis recall below 100%: {result.crisis_recall:.2%}"
                )
            if result.false_negative_count > 0:
                result.safety_issues.append(
                    f"False negatives detected: {result.false_negative_count}"
                )
            
        except Exception as e:
            logger.error("EVALUATION_ERROR", extra={"error": str(e)})
            result.safety_issues.append(f"Evaluation error: {str(e)}")
        
        result.completed_at = datetime.utcnow()
        
        # Save results
        if self.config.save_detailed_results:
            self._save_results(result)
        
        # Generate report
        if self.config.generate_report:
            self._generate_report(result)
        
        logger.info(
            "EVALUATION_COMPLETED",
            extra={
                "run_id": run_id,
                "total_samples": result.total_samples_evaluated,
                "accuracy": result.overall_accuracy,
                "crisis_recall": result.crisis_recall,
                "passes_safety": result.passes_safety_threshold,
            }
        )
        
        return result

    def _run_internal_benchmarks(self) -> Dict[str, Dict[str, Any]]:
        """Run evaluation against internal benchmarks."""
        from .benchmarks import BenchmarkLoader
        from .triage import ImmediateTriageEvaluator
        
        results = {}
        loader = BenchmarkLoader()
        
        if self.scanner:
            evaluator = ImmediateTriageEvaluator(
                scanner=self.scanner,
                benchmark_loader=loader,
            )
            
            # Run each benchmark suite
            for suite_name in ["crisis_detection", "adversarial_cases", 
                              "false_positives", "caution_cases"]:
                try:
                    suite_result = evaluator.evaluate_suite(suite_name)
                    results[suite_name] = {
                        "total": suite_result.metrics.total_cases,
                        "correct": suite_result.metrics.passed,
                        "crisis_tp": suite_result.metrics.crisis_detected,
                        "crisis_fp": suite_result.metrics.false_alarms,
                        "crisis_fn": suite_result.metrics.crisis_missed,
                        "latencies": suite_result.metrics.latencies_ms,
                        "pass_rate": suite_result.metrics.overall_accuracy,
                        "crisis_recall": suite_result.metrics.crisis_recall,
                    }
                except FileNotFoundError:
                    logger.warning(f"Benchmark suite {suite_name} not found")
                except Exception as e:
                    logger.error(f"Error running {suite_name}: {e}")
        
        return results
    
    def _run_external_datasets(self) -> Dict[str, Dict[str, Any]]:
        """Run evaluation against external datasets."""
        from .datasets import MentalChat16KLoader, PHQ9DatasetLoader, ClinicalDecisionLoader
        
        results = {}
        
        loaders = {
            "mentalchat16k": MentalChat16KLoader,
            "phq9_depression": PHQ9DatasetLoader,
            "clinical_decisions": ClinicalDecisionLoader,
        }
        
        for name in self.config.datasets_to_include:
            if name not in loaders:
                continue
            
            try:
                loader_class = loaders[name]
                loader = loader_class()
                
                # Configure max samples
                if self.config.max_samples_per_dataset:
                    loader.config.max_samples = self.config.max_samples_per_dataset
                
                samples = loader.load()
                stats = loader.get_stats()
                
                # Evaluate samples
                correct = 0
                total = len(samples)
                
                if self.scanner:
                    for sample in samples:
                        try:
                            scan_result = self.scanner.scan(
                                message_id=sample.sample_id,
                                text=sample.text,
                                student_id="eval_student",
                            )
                            
                            if scan_result.risk_level.value == sample.triage_level:
                                correct += 1
                        except Exception:
                            pass
                
                results[name] = {
                    "total": total,
                    "correct": correct,
                    "accuracy": correct / total if total > 0 else 0.0,
                    "category": name.split("_")[0],
                    "stats": stats.to_dict(),
                }
                
            except Exception as e:
                logger.error(f"Error loading dataset {name}: {e}")
                results[name] = {"error": str(e)}
        
        return results
    
    def _run_triage_evaluation(self) -> Dict[str, Dict[str, Any]]:
        """Run multi-tier triage evaluation."""
        from .triage import (
            ImmediateTriageEvaluator,
            SessionTriageEvaluator,
            LongitudinalTriageEvaluator,
        )
        
        results = {}
        
        # Immediate triage
        if self.scanner:
            try:
                evaluator = ImmediateTriageEvaluator(scanner=self.scanner)
                all_results = evaluator.evaluate_all()
                aggregate = evaluator.get_aggregate_metrics(all_results)
                results["immediate"] = aggregate.to_dict()
            except Exception as e:
                logger.error(f"Immediate triage error: {e}")
        
        # Session triage
        if self.analyzer:
            try:
                evaluator = SessionTriageEvaluator(analyzer=self.analyzer)
                session_result = evaluator.evaluate_suite()
                results["session"] = session_result.metrics.to_dict()
            except Exception as e:
                logger.error(f"Session triage error: {e}")
        
        # Longitudinal triage
        try:
            evaluator = LongitudinalTriageEvaluator()
            long_result = evaluator.evaluate_pattern_detection(num_samples_per_pattern=5)
            results["longitudinal"] = long_result.metrics.to_dict()
        except Exception as e:
            logger.error(f"Longitudinal triage error: {e}")
        
        return results
    
    def _run_test_suites(self) -> Dict[str, Dict[str, Any]]:
        """Run E2E, Integration, and Canary test suites."""
        from .suites import E2ETestSuite, IntegrationTestSuite, CanaryTestSuite
        
        results = {}
        
        # E2E tests
        try:
            suite = E2ETestSuite(safety_service=self.scanner)
            e2e_result = suite.run_all()
            results["e2e"] = e2e_result.to_dict()
        except Exception as e:
            logger.error(f"E2E suite error: {e}")
        
        # Integration tests
        try:
            suite = IntegrationTestSuite()
            int_result = suite.run_all()
            results["integration"] = int_result.to_dict()
        except Exception as e:
            logger.error(f"Integration suite error: {e}")
        
        # Canary tests
        try:
            suite = CanaryTestSuite(safety_service=self.scanner)
            canary_result = suite.run_all()
            results["canary"] = canary_result.to_dict()
        except Exception as e:
            logger.error(f"Canary suite error: {e}")
        
        return results

    def _save_results(self, result: EvaluationResult) -> None:
        """Save detailed results to file."""
        output_file = self.config.output_dir / f"{result.run_id}_results.json"
        
        with open(output_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        
        logger.info("RESULTS_SAVED", extra={"file": str(output_file)})
    
    def _generate_report(self, result: EvaluationResult) -> None:
        """Generate human-readable evaluation report."""
        report_file = self.config.output_dir / f"{result.run_id}_report.md"
        
        lines = [
            "# Feelwell Evaluation Report",
            "",
            f"**Run ID:** {result.run_id}",
            f"**Date:** {result.started_at.strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"**Duration:** {(result.completed_at - result.started_at).total_seconds():.1f} seconds",
            "",
            "## Safety Assessment",
            "",
            f"**Passes Safety Threshold:** {'✅ YES' if result.passes_safety_threshold else '❌ NO'}",
            "",
            f"- Crisis Recall: {result.crisis_recall:.2%} (must be 100%)",
            f"- False Negatives: {result.false_negative_count} (must be 0)",
            f"- Crisis Precision: {result.crisis_precision:.2%}",
            "",
        ]
        
        if result.safety_issues:
            lines.extend([
                "### ⚠️ Safety Issues",
                "",
            ])
            for issue in result.safety_issues:
                lines.append(f"- {issue}")
            lines.append("")
        
        lines.extend([
            "## Overall Metrics",
            "",
            f"- Total Samples Evaluated: {result.total_samples_evaluated:,}",
            f"- Overall Accuracy: {result.overall_accuracy:.2%}",
            f"- Average Latency: {result.avg_latency_ms:.1f}ms",
            f"- P99 Latency: {result.p99_latency_ms:.1f}ms",
            "",
            "## Results by Dataset",
            "",
            "| Dataset | Total | Accuracy | Notes |",
            "|---------|-------|----------|-------|",
        ])
        
        for name, metrics in result.metrics_by_dataset.items():
            if isinstance(metrics, dict) and "error" not in metrics:
                acc = metrics.get("accuracy", metrics.get("pass_rate", 0))
                lines.append(
                    f"| {name} | {metrics.get('total', 0):,} | {acc:.2%} | |"
                )
        
        lines.extend([
            "",
            "## Triage Evaluation",
            "",
        ])
        
        if result.immediate_triage_metrics:
            lines.extend([
                "### Immediate Triage (Real-time Crisis Detection)",
                "",
                f"- Crisis Recall: {result.immediate_triage_metrics.get('crisis_recall', 0):.2%}",
                f"- False Negative Rate: {result.immediate_triage_metrics.get('false_negative_rate', 0):.2%}",
                "",
            ])
        
        if result.session_triage_metrics:
            lines.extend([
                "### Session Triage (Mid-term Analysis)",
                "",
                f"- Trajectory Accuracy: {result.session_triage_metrics.get('trajectory_accuracy', 0):.2%}",
                f"- Escalation Recall: {result.session_triage_metrics.get('escalation_recall', 0):.2%}",
                "",
            ])
        
        if result.longitudinal_triage_metrics:
            lines.extend([
                "### Longitudinal Triage (Long-term Patterns)",
                "",
                f"- Pattern Accuracy: {result.longitudinal_triage_metrics.get('pattern_accuracy', 0):.2%}",
                f"- Early Warning Recall: {result.longitudinal_triage_metrics.get('early_warning_recall', 0):.2%}",
                "",
            ])
        
        lines.extend([
            "## Test Suites",
            "",
        ])
        
        if result.e2e_results:
            lines.append(f"- **E2E Tests:** {result.e2e_results.get('passed', 0)}/{result.e2e_results.get('total_tests', 0)} passed")
        if result.integration_results:
            lines.append(f"- **Integration Tests:** {result.integration_results.get('passed', 0)}/{result.integration_results.get('total_tests', 0)} passed")
        if result.canary_results:
            lines.append(f"- **Canary Tests:** {result.canary_results.get('passed', 0)}/{result.canary_results.get('total_scenarios', 0)} passed")
        
        lines.extend([
            "",
            "---",
            "",
            "*Generated by Feelwell Evaluation Platform*",
        ])
        
        with open(report_file, "w") as f:
            f.write("\n".join(lines))
        
        logger.info("REPORT_GENERATED", extra={"file": str(report_file)})


def run_evaluation(
    scanner=None,
    analyzer=None,
    config: Optional[EvaluationConfig] = None,
) -> EvaluationResult:
    """Convenience function to run evaluation.
    
    Args:
        scanner: SafetyScanner instance
        analyzer: MessageAnalyzer instance
        config: Evaluation configuration
        
    Returns:
        EvaluationResult
    """
    runner = EvaluationRunner(
        config=config,
        scanner=scanner,
        analyzer=analyzer,
    )
    return runner.run()
