"""MentalChat16K Evaluation Suite.

Comprehensive evaluation suite for testing LLM responses against
clinical metrics and safety requirements.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from datetime import datetime

from evaluation.evaluators.gpt4_evaluator import GPT4Evaluator, EvaluationConfig
from evaluation.metrics.mentalchat_metrics import ClinicalEvaluation
from evaluation.datasets.mentalchat16k_loader import MentalChat16KLoader

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """Single test case for evaluation."""
    id: str
    question: str
    expected_topics: List[str]
    source: str
    metadata: Optional[Dict] = None


@dataclass
class EvaluationResult:
    """Result of evaluating a model on test suite."""
    model_name: str
    timestamp: str
    test_cases_count: int
    evaluations: List[ClinicalEvaluation]
    summary: Dict
    pass_rate: float


class MentalChatEvaluationSuite:
    """Evaluation suite for mental health counseling models."""
    
    def __init__(
        self,
        gpt4_api_key: str,
        test_cases_path: Optional[str] = None
    ):
        """Initialize evaluation suite.
        
        Args:
            gpt4_api_key: OpenAI API key for GPT-4 evaluation
            test_cases_path: Optional path to custom test cases JSON
        """
        self.evaluator = GPT4Evaluator(
            EvaluationConfig(api_key=gpt4_api_key)
        )
        self.test_cases_path = test_cases_path
        self.test_cases: List[TestCase] = []
        
        logger.info("MentalChat evaluation suite initialized")
    
    def load_test_cases(
        self,
        count: int = 200,
        topics: Optional[List[str]] = None
    ) -> List[TestCase]:
        """Load test cases from MentalChat16K or custom file.
        
        Args:
            count: Number of test cases to load
            topics: Optional filter by topics
            
        Returns:
            List of TestCase objects
        """
        if self.test_cases_path and Path(self.test_cases_path).exists():
            # Load from custom file
            with open(self.test_cases_path, 'r') as f:
                data = json.load(f)
            
            self.test_cases = [
                TestCase(
                    id=case.get("id", f"test_{i}"),
                    question=case["question"],
                    expected_topics=case.get("topics", []),
                    source=case.get("source", "custom"),
                    metadata=case.get("metadata")
                )
                for i, case in enumerate(data[:count])
            ]
        else:
            # Load from MentalChat16K dataset
            loader = MentalChat16KLoader()
            conversations = loader.load_dataset()
            
            # Filter by topics if specified
            if topics:
                conversations = loader.filter_by_topics(conversations, topics)
            
            # Sample test cases
            import random
            sampled = random.sample(
                conversations,
                min(count, len(conversations))
            )
            
            self.test_cases = [
                TestCase(
                    id=f"mentalchat_{i}",
                    question=conv.input,
                    expected_topics=conv.topics or [],
                    source=conv.source.value,
                    metadata=conv.metadata
                )
                for i, conv in enumerate(sampled)
            ]
        
        logger.info(
            "Test cases loaded",
            extra={"count": len(self.test_cases)}
        )
        
        return self.test_cases
    
    async def evaluate_model(
        self,
        model_name: str,
        generate_response_fn,
        test_cases: Optional[List[TestCase]] = None,
        progress_callback=None
    ) -> EvaluationResult:
        """Evaluate a model on test cases.
        
        Args:
            model_name: Name of the model being evaluated
            generate_response_fn: Async function that takes question and returns response
            test_cases: Optional custom test cases (uses loaded if None)
            progress_callback: Optional callback function(increment) for progress updates
            
        Returns:
            EvaluationResult with complete evaluation data
        """
        if test_cases is None:
            test_cases = self.test_cases
        
        if not test_cases:
            raise ValueError("No test cases loaded. Call load_test_cases() first.")
        
        logger.info(
            "Starting model evaluation",
            extra={
                "model": model_name,
                "test_cases": len(test_cases)
            }
        )
        
        # Generate responses for all test cases
        responses = []
        for i, test_case in enumerate(test_cases):
            try:
                response = await generate_response_fn(test_case.question)
                responses.append(response)
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(1)
                
                if (i + 1) % 10 == 0:
                    logger.info(
                        "Progress update",
                        extra={
                            "completed": i + 1,
                            "total": len(test_cases)
                        }
                    )
            except Exception as e:
                logger.error(
                    "Response generation failed",
                    extra={
                        "test_case_id": test_case.id,
                        "error": str(e)
                    }
                )
                responses.append("ERROR: Failed to generate response")
                
                # Still update progress on error
                if progress_callback:
                    progress_callback(1)
        
        # Evaluate all responses
        eval_cases = [
            {"question": tc.question, "response": resp}
            for tc, resp in zip(test_cases, responses)
        ]
        
        evaluations = await self.evaluator.evaluate_batch(eval_cases)
        
        # Generate summary
        summary = self.evaluator.generate_report(evaluations)
        
        # Calculate pass rate
        pass_count = sum(
            1 for eval in evaluations
            if self.evaluator.metrics.check_minimum_thresholds(eval)
        )
        pass_rate = (pass_count / len(evaluations)) * 100 if evaluations else 0
        
        result = EvaluationResult(
            model_name=model_name,
            timestamp=datetime.utcnow().isoformat(),
            test_cases_count=len(test_cases),
            evaluations=evaluations,
            summary=summary,
            pass_rate=pass_rate
        )
        
        logger.info(
            "Model evaluation completed",
            extra={
                "model": model_name,
                "average_score": summary.get("overall_average"),
                "pass_rate": pass_rate
            }
        )
        
        return result
    
    def save_results(
        self,
        result: EvaluationResult,
        output_path: str
    ):
        """Save evaluation results to file.
        
        Args:
            result: Evaluation result to save
            output_path: Path to save results JSON
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert to serializable format
        data = {
            "model_name": result.model_name,
            "timestamp": result.timestamp,
            "test_cases_count": result.test_cases_count,
            "summary": result.summary,
            "pass_rate": result.pass_rate,
            "evaluations": [
                {
                    "question": eval.question[:200] + "...",  # Truncate for size
                    "response": eval.response[:200] + "...",
                    "average_score": eval.average_score,
                    "scores": [
                        {
                            "metric": score.metric.value,
                            "score": score.score,
                            "justification": score.justification
                        }
                        for score in eval.scores
                    ]
                }
                for eval in result.evaluations
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(
            "Results saved",
            extra={"output_path": str(output_path)}
        )
    
    def compare_models(
        self,
        results: List[EvaluationResult]
    ) -> Dict:
        """Compare multiple model evaluation results.
        
        Args:
            results: List of evaluation results to compare
            
        Returns:
            Dictionary with comparison statistics
        """
        comparison = {
            "models": [r.model_name for r in results],
            "timestamp": datetime.utcnow().isoformat(),
            "overall_scores": {
                r.model_name: r.summary.get("overall_average")
                for r in results
            },
            "pass_rates": {
                r.model_name: r.pass_rate
                for r in results
            },
            "metric_comparison": {}
        }
        
        # Compare each metric across models
        from ..metrics.mentalchat_metrics import ClinicalMetric
        
        for metric in ClinicalMetric:
            metric_name = metric.value
            comparison["metric_comparison"][metric_name] = {
                r.model_name: r.summary.get("metric_scores", {})
                    .get(metric_name, {})
                    .get("average")
                for r in results
            }
        
        # Determine best model
        best_model = max(
            results,
            key=lambda r: r.summary.get("overall_average", 0)
        )
        comparison["best_model"] = best_model.model_name
        comparison["best_score"] = best_model.summary.get("overall_average")
        
        logger.info(
            "Model comparison completed",
            extra={
                "num_models": len(results),
                "best_model": comparison["best_model"]
            }
        )
        
        return comparison


async def run_baseline_evaluation(
    gpt4_api_key: str,
    model_generate_fn,
    model_name: str = "baseline",
    output_dir: str = "./evaluation_results",
    progress_callback=None
):
    """Run baseline evaluation on a model.
    
    Args:
        gpt4_api_key: OpenAI API key for evaluation
        model_generate_fn: Async function to generate responses
        model_name: Name of the model
        output_dir: Directory to save results
        progress_callback: Optional callback function for progress updates
    """
    suite = MentalChatEvaluationSuite(gpt4_api_key)
    
    # Load 200 test cases (as per paper)
    suite.load_test_cases(count=200)
    
    # Evaluate model with progress tracking
    result = await suite.evaluate_model(
        model_name=model_name,
        generate_response_fn=model_generate_fn,
        progress_callback=progress_callback
    )
    
    # Save results
    output_path = Path(output_dir) / f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    suite.save_results(result, str(output_path))
    
    print(f"\n{'='*60}")
    print(f"Evaluation Results for {model_name}")
    print(f"{'='*60}")
    print(f"Test Cases: {result.test_cases_count}")
    print(f"Average Score: {result.summary.get('overall_average'):.2f}/10")
    print(f"Pass Rate: {result.pass_rate:.1f}%")
    print(f"\nMetric Scores:")
    for metric, scores in result.summary.get("metric_scores", {}).items():
        print(f"  {metric}: {scores.get('average'):.2f}/10")
    print(f"\nResults saved to: {output_path}")
    print(f"{'='*60}\n")
    
    return result
