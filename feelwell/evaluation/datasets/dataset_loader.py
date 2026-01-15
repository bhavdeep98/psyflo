"""Base dataset loader and configuration.

Provides common infrastructure for loading and processing
external clinical datasets for evaluation.
"""
import logging
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Iterator
import hashlib

logger = logging.getLogger(__name__)


class DatasetSource(Enum):
    """Source of dataset."""
    HUGGINGFACE = "huggingface"
    KAGGLE = "kaggle"
    GITHUB = "github"
    LOCAL = "local"
    ARXIV = "arxiv"


@dataclass
class DatasetConfig:
    """Configuration for dataset loading."""
    name: str
    source: DatasetSource
    source_url: str
    version: str = "1.0.0"
    
    # Local paths
    cache_dir: Path = field(default_factory=lambda: Path("feelwell/evaluation/datasets/cache"))
    processed_dir: Path = field(default_factory=lambda: Path("feelwell/evaluation/datasets/processed"))
    
    # Processing options
    max_samples: Optional[int] = None
    random_seed: int = 42
    train_split: float = 0.8
    
    # Category mapping
    category_mapping: Dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.processed_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class DatasetSample:
    """Single sample from a dataset."""
    sample_id: str
    text: str
    category: str  # Original category from dataset
    triage_level: str  # Mapped to safe/caution/crisis
    severity_score: Optional[float] = None
    
    # Metadata
    source_dataset: str = ""
    original_label: str = ""
    context: Optional[List[str]] = None  # For conversational data
    
    # Clinical scores if available
    phq9_score: Optional[int] = None
    gad7_score: Optional[int] = None
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sample_id": self.sample_id,
            "text": self.text,
            "category": self.category,
            "triage_level": self.triage_level,
            "severity_score": self.severity_score,
            "source_dataset": self.source_dataset,
            "phq9_score": self.phq9_score,
            "gad7_score": self.gad7_score,
        }


@dataclass
class DatasetStats:
    """Statistics about a loaded dataset."""
    total_samples: int
    samples_by_category: Dict[str, int]
    samples_by_triage: Dict[str, int]
    avg_text_length: float
    has_severity_scores: bool
    has_clinical_scores: bool
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_samples": self.total_samples,
            "samples_by_category": self.samples_by_category,
            "samples_by_triage": self.samples_by_triage,
            "avg_text_length": round(self.avg_text_length, 1),
            "has_severity_scores": self.has_severity_scores,
            "has_clinical_scores": self.has_clinical_scores,
        }


class DatasetLoader(ABC):
    """Abstract base class for dataset loaders."""
    
    def __init__(self, config: DatasetConfig):
        """Initialize loader with configuration.
        
        Args:
            config: Dataset configuration
        """
        self.config = config
        self._samples: List[DatasetSample] = []
        self._loaded = False
        
        logger.info(
            "DATASET_LOADER_INITIALIZED",
            extra={
                "dataset": config.name,
                "source": config.source.value,
            }
        )
    
    @abstractmethod
    def download(self) -> bool:
        """Download dataset from source.
        
        Returns:
            True if download successful
        """
        pass
    
    @abstractmethod
    def process(self) -> List[DatasetSample]:
        """Process raw data into DatasetSamples.
        
        Returns:
            List of processed samples
        """
        pass
    
    def load(self, force_reload: bool = False) -> List[DatasetSample]:
        """Load dataset, downloading if necessary.
        
        Args:
            force_reload: Force re-download and reprocess
            
        Returns:
            List of DatasetSample
        """
        processed_file = self.config.processed_dir / f"{self.config.name}_processed.json"
        
        # Check for cached processed data
        if not force_reload and processed_file.exists():
            logger.info(f"Loading cached processed data from {processed_file}")
            self._samples = self._load_processed(processed_file)
            self._loaded = True
            return self._samples
        
        # Download if needed
        if not self._is_downloaded():
            logger.info(f"Downloading dataset {self.config.name}")
            success = self.download()
            if not success:
                raise RuntimeError(f"Failed to download dataset {self.config.name}")
        
        # Process
        logger.info(f"Processing dataset {self.config.name}")
        self._samples = self.process()
        
        # Apply max_samples limit
        if self.config.max_samples and len(self._samples) > self.config.max_samples:
            import random
            random.seed(self.config.random_seed)
            self._samples = random.sample(self._samples, self.config.max_samples)
        
        # Cache processed data
        self._save_processed(processed_file)
        
        self._loaded = True
        
        logger.info(
            "DATASET_LOADED",
            extra={
                "dataset": self.config.name,
                "samples": len(self._samples),
            }
        )
        
        return self._samples
    
    def _is_downloaded(self) -> bool:
        """Check if dataset is already downloaded."""
        cache_file = self.config.cache_dir / f"{self.config.name}_raw"
        return cache_file.exists() or (self.config.cache_dir / self.config.name).exists()
    
    def _load_processed(self, path: Path) -> List[DatasetSample]:
        """Load processed samples from JSON."""
        with open(path, "r") as f:
            data = json.load(f)
        
        samples = []
        for item in data["samples"]:
            samples.append(DatasetSample(
                sample_id=item["sample_id"],
                text=item["text"],
                category=item["category"],
                triage_level=item["triage_level"],
                severity_score=item.get("severity_score"),
                source_dataset=item.get("source_dataset", self.config.name),
                original_label=item.get("original_label", ""),
                context=item.get("context"),
                phq9_score=item.get("phq9_score"),
                gad7_score=item.get("gad7_score"),
                metadata=item.get("metadata", {}),
            ))
        
        return samples
    
    def _save_processed(self, path: Path) -> None:
        """Save processed samples to JSON."""
        data = {
            "dataset": self.config.name,
            "version": self.config.version,
            "processed_at": datetime.utcnow().isoformat(),
            "samples": [s.to_dict() for s in self._samples],
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    def get_stats(self) -> DatasetStats:
        """Get statistics about loaded dataset."""
        if not self._loaded:
            self.load()
        
        samples_by_category: Dict[str, int] = {}
        samples_by_triage: Dict[str, int] = {}
        total_length = 0
        has_severity = False
        has_clinical = False
        
        for sample in self._samples:
            # Category counts
            samples_by_category[sample.category] = samples_by_category.get(sample.category, 0) + 1
            samples_by_triage[sample.triage_level] = samples_by_triage.get(sample.triage_level, 0) + 1
            
            # Text length
            total_length += len(sample.text)
            
            # Score availability
            if sample.severity_score is not None:
                has_severity = True
            if sample.phq9_score is not None or sample.gad7_score is not None:
                has_clinical = True
        
        return DatasetStats(
            total_samples=len(self._samples),
            samples_by_category=samples_by_category,
            samples_by_triage=samples_by_triage,
            avg_text_length=total_length / len(self._samples) if self._samples else 0,
            has_severity_scores=has_severity,
            has_clinical_scores=has_clinical,
        )
    
    def get_by_triage(self, triage_level: str) -> List[DatasetSample]:
        """Get samples by triage level.
        
        Args:
            triage_level: safe, caution, or crisis
            
        Returns:
            Filtered list of samples
        """
        if not self._loaded:
            self.load()
        return [s for s in self._samples if s.triage_level == triage_level]
    
    def get_by_category(self, category: str) -> List[DatasetSample]:
        """Get samples by category.
        
        Args:
            category: Category name (e.g., depression, anxiety)
            
        Returns:
            Filtered list of samples
        """
        if not self._loaded:
            self.load()
        return [s for s in self._samples if s.category == category]
    
    def iter_samples(self) -> Iterator[DatasetSample]:
        """Iterate over samples."""
        if not self._loaded:
            self.load()
        yield from self._samples
    
    def split_train_test(self) -> tuple:
        """Split dataset into train and test sets.
        
        Returns:
            Tuple of (train_samples, test_samples)
        """
        if not self._loaded:
            self.load()
        
        import random
        random.seed(self.config.random_seed)
        
        shuffled = self._samples.copy()
        random.shuffle(shuffled)
        
        split_idx = int(len(shuffled) * self.config.train_split)
        
        return shuffled[:split_idx], shuffled[split_idx:]
    
    @property
    def samples(self) -> List[DatasetSample]:
        if not self._loaded:
            self.load()
        return self._samples
