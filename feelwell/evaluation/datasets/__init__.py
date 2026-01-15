"""External dataset loaders and processors.

Integrates published clinical benchmarks:
- MentalChat16K: Conversational counseling benchmark
- PHQ-9: Depression severity assessment
- PHQ-9 Longitudinal: Time-series mood dynamics
- GAD-7: Anxiety severity assessment
- Clinical Decision Tasks: Triage reasoning benchmark

All datasets are processed to align with Feelwell's triage categories:
- SAFE: No immediate intervention needed
- CAUTION: Monitor, may need follow-up
- CRISIS: Immediate intervention required
"""
from .dataset_loader import DatasetLoader, DatasetConfig
from .mentalchat16k import MentalChat16KLoader
from .phq9_dataset import PHQ9DatasetLoader
from .phq9_longitudinal import PHQ9LongitudinalLoader, PHQ9LongitudinalConfig, PHQ9TimeSeriesSample
from .clinical_decisions import ClinicalDecisionLoader
from .category_mapper import CategoryMapper, TriageCategory

__all__ = [
    "DatasetLoader",
    "DatasetConfig",
    "MentalChat16KLoader",
    "PHQ9DatasetLoader",
    "PHQ9LongitudinalLoader",
    "PHQ9LongitudinalConfig",
    "PHQ9TimeSeriesSample",
    "ClinicalDecisionLoader",
    "CategoryMapper",
    "TriageCategory",
]
