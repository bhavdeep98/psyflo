"""Integration tests for MentalChat16K evaluation framework.

Tests the complete evaluation pipeline from dataset loading to
metric evaluation and report generation.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch

from ..datasets.mentalchat16k_loader import (
    MentalChat16KLoader,
    MentalHealthConversation,
    DatasetType,
    StudentScenarioAugmenter
)
from ..metrics.mentalchat_metrics import (
    MentalChatMetrics,
    ClinicalMetric,
    MetricScore,
    ClinicalEvaluation
)
from ..evaluators.gpt4_evaluator import GPT4Evaluator, EvaluationConfig
from ..suites.mentalchat_eval import MentalChatEvaluationSuite, TestCase


class TestMentalChat16KLoader:
    """Test dataset loading and processing."""
    
    def test_loader_initialization(self):
        """Test loader initializes correctly."""
        loader = MentalChat16KLoader(cache_dir="./test_cache")
        assert loader.cache_dir.name == "test_cache"
    
    def test_determine_source(self):
        """Test source determination logic."""
        loader = MentalChat16KLoader()
        
        # Short input = interview data
        interview_item = {"input": "I've been feeling sad.", "output": "..."}
        assert loader._determine_source(interview_item) == DatasetType.INTERVIEW
        
        # Long input = synthetic data
        synthetic_item = {
            "input": " ".join(["word"] * 120),
            "output": "..."
        }
        assert loader._determine_source(synthetic_item) == DatasetType.SYNTHETIC
    
    def test_extract_topics(self):
        """Test topic extraction from conversations."""
        loader = MentalChat16KLoader()
        
        item = {
            "input": "I've been feeling very anxious and depressed lately.",
            "output": "I understand you're dealing with anxiety and depression."
        }
        
        topics = loader._extract_topics(item)
        assert "anxiety" in topics
        assert "depression" in topics
    
    def test_filter_by_topics(self):
        """Test filtering conversations by topics."""
        loader = MentalChat16KLoader()
        
        conversations = [
            MentalHealthConversation(
                instruction="",
                input="",
                output="",
                source=DatasetType.SYNTHETIC,
                topics=["anxiety", "stress"]
            ),
            MentalHealthConversation(
                instruction="",
                input="",
                output="",
                source=DatasetType.SYNTHETIC,
                topics=["depression"]
            )
        ]
        
        filtered = loader.filter_by_topics(conversations, ["anxiety"])
        assert len(filtered) == 1
        assert "anxiety" in filtered[0].topics


class TestMentalChatMetrics:
    """Test clinical metrics implementation."""
    
    def test_metrics_initialization(self):
        """Test metrics evaluator initializes correctly."""
        metrics = MentalChatMetrics()
        assert len(metrics.get_all_metrics()) == 7
    
    def test_get_metric_definition(self):
        """Test retrieving metric definitions."""
        metrics = MentalChatMetrics()
        
        definition = metrics.get_metric_definition(ClinicalMetric.ACTIVE_LISTENING)
        assert "Active Listening" in definition["name"]
        assert len(definition["criteria"]) > 0
    
    def test_create_evaluation_prompt(self):
        """Test evaluation prompt generation."""
        metrics = MentalChatMetrics()
        
        prompt = metrics.create_evaluation_prompt(
            question="I'm feeling anxious",
            response="I understand your anxiety",
            metric=ClinicalMetric.EMPATHY_VALIDATION
        )
        
        assert "Empathy & Validation" in prompt
        assert "I'm feeling anxious" in prompt
        assert "I understand your anxiety" in prompt
        assert "Score:" in prompt
    
    def test_parse_llm_evaluation(self):
        """Test parsing LLM evaluation responses."""
        metrics = MentalChatMetrics()
        
        llm_response = """Score: 8/10
Justification: The response demonstrates good empathy and validation."""
        
        score = metrics.parse_llm_evaluation(
            llm_response=llm_response,
            metric=ClinicalMetric.EMPATHY_VALIDATION,
            evaluator="gpt4"
        )
        
        assert score.score == 8.0
        assert "empathy" in score.justification.lower()
        assert score.evaluator == "gpt4"
    
    def test_parse_llm_evaluation_invalid(self):
        """Test parsing invalid LLM responses."""
        metrics = MentalChatMetrics()
        
        with pytest.raises(ValueError):
            metrics.parse_llm_evaluation(
                llm_response="Invalid response",
                metric=ClinicalMetric.EMPATHY_VALIDATION,
                evaluator="gpt4"
            )
    
    def test_calculate_average_score(self):
        """Test average score calculation."""
        metrics = MentalChatMetrics()
        
        scores = [
            MetricScore(
                metric=ClinicalMetric.ACTIVE_LISTENING,
                score=8.0,
                justification="Good",
                evaluator="gpt4"
            ),
            MetricScore(
                metric=ClinicalMetric.EMPATHY_VALIDATION,
                score=7.0,
                justification="Fair",
                evaluator="gpt4"
            )
        ]
        
        avg = metrics.calculate_average_score(scores)
        assert avg == 7.5
    
    def test_check_minimum_thresholds(self):
        """Test threshold checking."""
        metrics = MentalChatMetrics()
        
        # Create evaluation that passes thresholds
        scores = [
            MetricScore(
                metric=ClinicalMetric.SAFETY_TRUSTWORTHINESS,
                score=9.0,
                justification="Excellent",
                evaluator="gpt4"
            ),
            MetricScore(
                metric=ClinicalMetric.EMPATHY_VALIDATION,
                score=8.0,
                justification="Good",
                evaluator="gpt4"
            )
        ]
        
        evaluation = metrics.evaluate_response(
            question="Test question",
            response="Test response",
            scores=scores
        )
        
        assert metrics.check_minimum_thresholds(evaluation)
        
        # Create evaluation that fails thresholds
        low_scores = [
            MetricScore(
                metric=ClinicalMetric.SAFETY_TRUSTWORTHINESS,
                score=6.0,
                justification="Below threshold",
                evaluator="gpt4"
            )
        ]
        
        low_evaluation = metrics.evaluate_response(
            question="Test question",
            response="Test response",
            scores=low_scores
        )
        
        assert not metrics.check_minimum_thresholds(low_evaluation)


class TestStudentScenarioAugmenter:
    """Test student scenario augmentation."""
    
    def test_augmenter_initialization(self):
        """Test augmenter initializes with scenarios."""
        augmenter = StudentScenarioAugmenter()
        assert len(augmenter.STUDENT_SCENARIOS) > 0
    
    def test_augment_dataset(self):
        """Test dataset augmentation."""
        augmenter = StudentScenarioAugmenter()
        
        base_conversations = [
            MentalHealthConversation(
                instruction="",
                input="Test input",
                output="Test output",
                source=DatasetType.SYNTHETIC
            )
        ]
        
        augmented = augmenter.augment_dataset(base_conversations)
        
        assert len(augmented) > len(base_conversations)
        
        # Check that student scenarios were added
        student_convs = [
            conv for conv in augmented
            if conv.source == DatasetType.STUDENT_AUGMENTED
        ]
        assert len(student_convs) > 0


@pytest.mark.asyncio
class TestGPT4Evaluator:
    """Test GPT-4 evaluator (requires mocking)."""
    
    async def test_evaluator_initialization(self):
        """Test evaluator initializes correctly."""
        config = EvaluationConfig(api_key="test-key")
        evaluator = GPT4Evaluator(config)
        
        assert evaluator.config.api_key == "test-key"
        assert evaluator.metrics is not None
    
    @patch('services.llm_service.base_llm.OpenAILLM.generate')
    async def test_evaluate_single_metric(self, mock_generate):
        """Test single metric evaluation."""
        # Mock LLM response
        mock_generate.return_value = AsyncMock(
            text="Score: 8/10\nJustification: Good empathy shown."
        )
        
        config = EvaluationConfig(api_key="test-key")
        evaluator = GPT4Evaluator(config)
        
        score = await evaluator.evaluate_single_metric(
            question="I'm feeling anxious",
            response="I understand your anxiety",
            metric=ClinicalMetric.EMPATHY_VALIDATION
        )
        
        assert score.score == 8.0
        assert score.metric == ClinicalMetric.EMPATHY_VALIDATION


class TestMentalChatEvaluationSuite:
    """Test evaluation suite."""
    
    def test_suite_initialization(self):
        """Test suite initializes correctly."""
        suite = MentalChatEvaluationSuite(gpt4_api_key="test-key")
        assert suite.evaluator is not None
    
    def test_load_test_cases_from_scenarios(self):
        """Test loading test cases from student scenarios."""
        suite = MentalChatEvaluationSuite(gpt4_api_key="test-key")
        
        # Mock the dataset loading
        with patch.object(MentalChat16KLoader, 'load_dataset') as mock_load:
            mock_load.return_value = [
                MentalHealthConversation(
                    instruction="",
                    input="Test question",
                    output="Test response",
                    source=DatasetType.SYNTHETIC,
                    topics=["anxiety"]
                )
            ]
            
            test_cases = suite.load_test_cases(count=1)
            
            assert len(test_cases) == 1
            assert isinstance(test_cases[0], TestCase)


def test_integration_workflow():
    """Test complete integration workflow (without API calls)."""
    # 1. Load dataset
    loader = MentalChat16KLoader()
    
    # 2. Create test conversation
    conversation = MentalHealthConversation(
        instruction="You are a helpful counselor",
        input="I've been feeling very anxious lately",
        output="I understand that anxiety can be overwhelming",
        source=DatasetType.SYNTHETIC,
        topics=["anxiety"]
    )
    
    # 3. Initialize metrics
    metrics = MentalChatMetrics()
    
    # 4. Create mock evaluation
    scores = [
        MetricScore(
            metric=metric,
            score=8.0,
            justification="Good response",
            evaluator="test"
        )
        for metric in metrics.get_all_metrics()
    ]
    
    evaluation = metrics.evaluate_response(
        question=conversation.input,
        response=conversation.output,
        scores=scores
    )
    
    # 5. Verify evaluation
    assert evaluation.average_score == 8.0
    assert len(evaluation.scores) == 7
    assert metrics.check_minimum_thresholds(evaluation)
    
    # 6. Generate report
    report = metrics.generate_evaluation_report([evaluation])
    assert report["total_evaluations"] == 1
    assert report["overall_average"] == 8.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
