"""Feelwell Validation & Evaluation Platform.

Comprehensive testing harness for validating the safety pipeline,
crisis detection, sentiment analysis, and all backend services.

Components:
- benchmarks/: Curated test datasets with expected outcomes
- scenarios/: Canary tests (realistic user journeys)
- suites/: E2E, Integration, and Canary test runners
- rag/: RAG evaluation for long-term pattern analysis
- triage/: Multi-tier triage testing (immediate/session/longitudinal)
- api/: REST API for the Test Console webapp
"""
from .runner import EvaluationRunner, EvaluationConfig, run_evaluation

__all__ = [
    "EvaluationRunner",
    "EvaluationConfig",
    "run_evaluation",
]
