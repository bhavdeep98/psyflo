"""GPT-4 Evaluator for Clinical Metrics.

Uses GPT-4 Turbo as an automated judge to evaluate mental health counseling
responses based on the 7 clinical metrics from MentalChat16K paper.
"""

import logging
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass

from evaluation.metrics.mentalchat_metrics import (
    MentalChatMetrics,
    ClinicalMetric,
    MetricScore,
    ClinicalEvaluation
)
from services.llm_service.base_llm import (
    OpenAILLM,
    LLMConfig,
    LLMProvider
)

logger = logging.getLogger(__name__)


@dataclass
class EvaluationConfig:
    """Configuration for GPT-4 evaluation."""
    api_key: str
    model: str = "gpt-4-turbo-preview"
    max_concurrent: int = 5
    timeout_seconds: int = 60


class GPT4Evaluator:
    """Evaluates counseling responses using GPT-4 as a judge."""
    
    def __init__(self, config: EvaluationConfig):
        """Initialize GPT-4 evaluator.
        
        Args:
            config: Evaluation configuration
        """
        self.config = config
        self.metrics = MentalChatMetrics()
        
        # Initialize GPT-4 client
        llm_config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model_name=config.model,
            api_key=config.api_key,
            max_tokens=500,
            temperature=0.3,  # Lower temperature for consistent evaluation
            timeout_seconds=config.timeout_seconds
        )
        self.llm = OpenAILLM(llm_config)
        
        # Semaphore for rate limiting
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        
        logger.info(
            "GPT-4 evaluator initialized",
            extra={"model": config.model}
        )
    
    async def evaluate_single_metric(
        self,
        question: str,
        response: str,
        metric: ClinicalMetric
    ) -> MetricScore:
        """Evaluate a response on a single clinical metric.
        
        Args:
            question: The user's question
            response: The counselor's response to evaluate
            metric: The clinical metric to evaluate
            
        Returns:
            MetricScore object
        """
        async with self.semaphore:
            # Create evaluation prompt
            prompt = self.metrics.create_evaluation_prompt(
                question=question,
                response=response,
                metric=metric
            )
            
            try:
                # Get GPT-4 evaluation
                llm_response = await self.llm.generate(prompt)
                
                # Parse the evaluation
                score = self.metrics.parse_llm_evaluation(
                    llm_response=llm_response.text,
                    metric=metric,
                    evaluator="gpt4"
                )
                
                logger.info(
                    "Metric evaluation completed",
                    extra={
                        "metric": metric.value,
                        "score": score.score
                    }
                )
                
                return score
                
            except Exception as e:
                logger.error(
                    "Metric evaluation failed",
                    extra={
                        "metric": metric.value,
                        "error": str(e)
                    }
                )
                raise
    
    async def evaluate_all_metrics(
        self,
        question: str,
        response: str
    ) -> List[MetricScore]:
        """Evaluate a response on all 7 clinical metrics.
        
        Args:
            question: The user's question
            response: The counselor's response to evaluate
            
        Returns:
            List of MetricScore objects (one per metric)
        """
        logger.info("Starting full clinical evaluation")
        
        # Create tasks for all metrics
        tasks = [
            self.evaluate_single_metric(question, response, metric)
            for metric in self.metrics.get_all_metrics()
        ]
        
        # Execute in parallel with rate limiting
        scores = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out any exceptions
        valid_scores = [
            score for score in scores
            if isinstance(score, MetricScore)
        ]
        
        if len(valid_scores) < len(tasks):
            logger.warning(
                "Some metric evaluations failed",
                extra={
                    "successful": len(valid_scores),
                    "total": len(tasks)
                }
            )
        
        return valid_scores
    
    async def evaluate_response(
        self,
        question: str,
        response: str
    ) -> ClinicalEvaluation:
        """Complete evaluation of a counseling response.
        
        Args:
            question: The user's question
            response: The counselor's response to evaluate
            
        Returns:
            ClinicalEvaluation object with all metric scores
        """
        # Get scores for all metrics
        scores = await self.evaluate_all_metrics(question, response)
        
        # Create complete evaluation
        evaluation = self.metrics.evaluate_response(
            question=question,
            response=response,
            scores=scores
        )
        
        logger.info(
            "Clinical evaluation completed",
            extra={
                "average_score": evaluation.average_score,
                "num_metrics": len(scores)
            }
        )
        
        return evaluation
    
    async def evaluate_batch(
        self,
        test_cases: List[Dict[str, str]]
    ) -> List[ClinicalEvaluation]:
        """Evaluate multiple test cases.
        
        Args:
            test_cases: List of dicts with 'question' and 'response' keys
            
        Returns:
            List of ClinicalEvaluation objects
        """
        logger.info(
            "Starting batch evaluation",
            extra={"num_cases": len(test_cases)}
        )
        
        tasks = [
            self.evaluate_response(
                question=case["question"],
                response=case["response"]
            )
            for case in test_cases
        ]
        
        evaluations = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_evaluations = [
            eval for eval in evaluations
            if isinstance(eval, ClinicalEvaluation)
        ]
        
        logger.info(
            "Batch evaluation completed",
            extra={
                "successful": len(valid_evaluations),
                "total": len(test_cases)
            }
        )
        
        return valid_evaluations
    
    def generate_report(
        self,
        evaluations: List[ClinicalEvaluation]
    ) -> Dict:
        """Generate evaluation report with statistics.
        
        Args:
            evaluations: List of clinical evaluations
            
        Returns:
            Dictionary with evaluation statistics
        """
        return self.metrics.generate_evaluation_report(evaluations)
