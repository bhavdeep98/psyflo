"""Baseline experiment configuration.

Establishes baseline metrics against all benchmarks and datasets.
Run this before any model changes to establish comparison point.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from feelwell.evaluation.runner import EvaluationRunner, EvaluationConfig
from feelwell.evaluation.datasets import (
    MentalChat16KLoader,
    PHQ9DatasetLoader,
    ClinicalDecisionLoader,
)

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for baseline experiment."""
    name: str = "baseline"
    description: str = "Baseline evaluation against all benchmarks"
    
    # Datasets
    include_mentalchat: bool = True
    include_phq9: bool = True
    include_clinical: bool = True
    max_samples_per_dataset: int = 500
    
    # Evaluation
    run_safety_critical: bool = True
    run_category_breakdown: bool = True
    run_robustness_tests: bool = True
    
    # Output
    output_dir: Path = Path("feelwell/evaluation/results/baseline")


class BaselineExperiment:
    """Runs baseline evaluation experiment."""
    
    def __init__(
        self,
        config: Optional[ExperimentConfig] = None,
        scanner=None,
        analyzer=None,
    ):
        self.config = config or ExperimentConfig()
        self.scanner = scanner
        self.analyzer = analyzer
        
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
    
    def run(self) -> Dict[str, Any]:
        """Run baseline experiment.
        
        Returns:
            Dictionary with all results
        """
        logger.info(f"Starting baseline experiment: {self.config.name}")
        started_at = datetime.utcnow()
        
        results = {
            "experiment": self.config.name,
            "started_at": started_at.isoformat(),
            "config": {
                "max_samples": self.config.max_samples_per_dataset,
            },
        }
        
        # 1. Safety-critical evaluation
        if self.config.run_safety_critical:
            logger.info("Running safety-critical evaluation...")
            safety_results = self._run_safety_evaluation()
            results["safety"] = safety_results
        
        # 2. Dataset evaluations
        dataset_results = {}
        
        if self.config.include_mentalchat:
            logger.info("Evaluating MentalChat16K...")
            dataset_results["mentalchat16k"] = self._evaluate_dataset(
                MentalChat16KLoader()
            )
        
        if self.config.include_phq9:
            logger.info("Evaluating PHQ-9...")
            dataset_results["phq9"] = self._evaluate_dataset(
                PHQ9DatasetLoader()
            )
        
        if self.config.include_clinical:
            logger.info("Evaluating Clinical Decisions...")
            dataset_results["clinical"] = self._evaluate_dataset(
                ClinicalDecisionLoader()
            )
        
        results["datasets"] = dataset_results
        
        # 3. Category breakdown
        if self.config.run_category_breakdown:
            logger.info("Running category breakdown...")
            results["categories"] = self._run_category_breakdown(dataset_results)
        
        # 4. Robustness tests
        if self.config.run_robustness_tests:
            logger.info("Running robustness tests...")
            results["robustness"] = self._run_robustness_tests()
        
        # Finalize
        completed_at = datetime.utcnow()
        results["completed_at"] = completed_at.isoformat()
        results["duration_seconds"] = (completed_at - started_at).total_seconds()
        
        # Save results
        self._save_results(results)
        
        # Print summary
        self._print_summary(results)
        
        return results
    
    def _run_safety_evaluation(self) -> Dict[str, Any]:
        """Run safety-critical tests."""
        from feelwell.evaluation.triage import ImmediateTriageEvaluator
        from feelwell.evaluation.benchmarks import BenchmarkLoader
        
        if not self.scanner:
            return {"error": "Scanner not available"}
        
        evaluator = ImmediateTriageEvaluator(
            scanner=self.scanner,
            benchmark_loader=BenchmarkLoader(),
        )
        
        # Run crisis detection benchmark
        try:
            crisis_result = evaluator.evaluate_suite("crisis_detection")
            adversarial_result = evaluator.evaluate_suite("adversarial_cases")
            
            return {
                "crisis_detection": {
                    "total": crisis_result.metrics.total_cases,
                    "crisis_recall": crisis_result.metrics.crisis_recall,
                    "false_negatives": crisis_result.metrics.crisis_missed,
                    "passes": crisis_result.metrics.passes_safety_threshold,
                },
                "adversarial": {
                    "total": adversarial_result.metrics.total_cases,
                    "crisis_recall": adversarial_result.metrics.crisis_recall,
                    "false_negatives": adversarial_result.metrics.crisis_missed,
                },
                "overall_passes": (
                    crisis_result.metrics.passes_safety_threshold and
                    adversarial_result.metrics.crisis_recall >= 0.9
                ),
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _evaluate_dataset(self, loader) -> Dict[str, Any]:
        """Evaluate a single dataset."""
        try:
            loader.config.max_samples = self.config.max_samples_per_dataset
            samples = loader.load()
            stats = loader.get_stats()
            
            # Evaluate with scanner
            correct = 0
            by_triage = {"safe": 0, "caution": 0, "crisis": 0}
            correct_by_triage = {"safe": 0, "caution": 0, "crisis": 0}
            
            if self.scanner:
                for sample in samples:
                    by_triage[sample.triage_level] = by_triage.get(sample.triage_level, 0) + 1
                    
                    try:
                        result = self.scanner.scan(
                            message_id=sample.sample_id,
                            text=sample.text,
                            student_id="eval",
                        )
                        
                        if result.risk_level.value == sample.triage_level:
                            correct += 1
                            correct_by_triage[sample.triage_level] += 1
                    except Exception:
                        pass
            
            return {
                "total": len(samples),
                "accuracy": correct / len(samples) if samples else 0,
                "by_triage": by_triage,
                "accuracy_by_triage": {
                    k: correct_by_triage[k] / by_triage[k] if by_triage[k] > 0 else 0
                    for k in by_triage
                },
                "stats": stats.to_dict(),
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _run_category_breakdown(
        self,
        dataset_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Aggregate results by category."""
        categories = {}
        
        for dataset_name, results in dataset_results.items():
            if "error" in results:
                continue
            
            # Map dataset to category
            if "mentalchat" in dataset_name:
                cat = "conversational"
            elif "phq9" in dataset_name:
                cat = "depression"
            elif "clinical" in dataset_name:
                cat = "clinical_decision"
            else:
                cat = "other"
            
            if cat not in categories:
                categories[cat] = {"total": 0, "correct": 0}
            
            categories[cat]["total"] += results.get("total", 0)
            categories[cat]["correct"] += int(
                results.get("accuracy", 0) * results.get("total", 0)
            )
        
        # Calculate accuracy per category
        for cat in categories:
            total = categories[cat]["total"]
            correct = categories[cat]["correct"]
            categories[cat]["accuracy"] = correct / total if total > 0 else 0
        
        return categories
    
    def _run_robustness_tests(self) -> Dict[str, Any]:
        """Run robustness/adversarial tests."""
        from feelwell.evaluation.triage import ImmediateTriageEvaluator
        from feelwell.evaluation.benchmarks import BenchmarkLoader
        
        if not self.scanner:
            return {"error": "Scanner not available"}
        
        evaluator = ImmediateTriageEvaluator(
            scanner=self.scanner,
            benchmark_loader=BenchmarkLoader(),
        )
        
        results = {}
        
        for suite_name in ["adversarial_cases", "false_positives"]:
            try:
                suite_result = evaluator.evaluate_suite(suite_name)
                results[suite_name] = {
                    "total": suite_result.metrics.total_cases,
                    "passed": suite_result.metrics.passed,
                    "accuracy": suite_result.metrics.overall_accuracy,
                }
            except Exception as e:
                results[suite_name] = {"error": str(e)}
        
        return results
    
    def _save_results(self, results: Dict[str, Any]) -> None:
        """Save results to file."""
        import json
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_file = self.config.output_dir / f"baseline_{timestamp}.json"
        
        with open(output_file, "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info(f"Results saved to {output_file}")
    
    def _print_summary(self, results: Dict[str, Any]) -> None:
        """Print experiment summary."""
        print("\n" + "=" * 60)
        print("BASELINE EXPERIMENT RESULTS")
        print("=" * 60)
        
        # Safety
        if "safety" in results:
            safety = results["safety"]
            if "error" not in safety:
                print(f"\n🔒 Safety Evaluation:")
                print(f"   Crisis Recall: {safety.get('crisis_detection', {}).get('crisis_recall', 0):.2%}")
                print(f"   False Negatives: {safety.get('crisis_detection', {}).get('false_negatives', 'N/A')}")
                print(f"   Passes: {'✅' if safety.get('overall_passes') else '❌'}")
        
        # Datasets
        if "datasets" in results:
            print(f"\n📊 Dataset Evaluation:")
            for name, data in results["datasets"].items():
                if "error" not in data:
                    print(f"   {name}: {data.get('accuracy', 0):.2%} ({data.get('total', 0)} samples)")
        
        # Categories
        if "categories" in results:
            print(f"\n📁 By Category:")
            for cat, data in results["categories"].items():
                print(f"   {cat}: {data.get('accuracy', 0):.2%}")
        
        print("\n" + "=" * 60)


def run_baseline(scanner=None, analyzer=None) -> Dict[str, Any]:
    """Convenience function to run baseline experiment."""
    experiment = BaselineExperiment(scanner=scanner, analyzer=analyzer)
    return experiment.run()
