"""PHQ-9 Depression Assessment dataset loader.

Loads PHQ-9 depression severity data from Kaggle.
Source: https://www.kaggle.com/datasets/thedevastator/phq-9-depression-assessment

PHQ-9 Scoring:
- 0-4: Minimal depression
- 5-9: Mild depression  
- 10-14: Moderate depression
- 15-19: Moderately severe depression
- 20-27: Severe depression

Item 9 (suicidal ideation) requires special handling - any positive
response triggers crisis-level triage per clinical guidelines.
"""
import logging
import json
import csv
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from .dataset_loader import DatasetLoader, DatasetConfig, DatasetSample, DatasetSource
from .category_mapper import CategoryMapper, PHQ9Thresholds, TriageCategory

logger = logging.getLogger(__name__)


class PHQ9Config(DatasetConfig):
    """Configuration for PHQ-9 dataset."""
    
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        max_samples: Optional[int] = None,
    ):
        super().__init__(
            name="phq9_depression",
            source=DatasetSource.KAGGLE,
            source_url="https://www.kaggle.com/datasets/thedevastator/phq-9-depression-assessment",
            version="1.0.0",
            cache_dir=cache_dir or Path("feelwell/evaluation/datasets/cache"),
            max_samples=max_samples,
        )


# PHQ-9 Item descriptions for generating text samples
PHQ9_ITEMS = {
    1: "Little interest or pleasure in doing things",
    2: "Feeling down, depressed, or hopeless",
    3: "Trouble falling or staying asleep, or sleeping too much",
    4: "Feeling tired or having little energy",
    5: "Poor appetite or overeating",
    6: "Feeling bad about yourself - or that you are a failure",
    7: "Trouble concentrating on things",
    8: "Moving or speaking slowly, or being fidgety/restless",
    9: "Thoughts that you would be better off dead, or of hurting yourself",
}

# Response options
PHQ9_RESPONSES = {
    0: "Not at all",
    1: "Several days",
    2: "More than half the days",
    3: "Nearly every day",
}

# Severity labels
PHQ9_SEVERITY = {
    "minimal": (0, 4),
    "mild": (5, 9),
    "moderate": (10, 14),
    "moderately_severe": (15, 19),
    "severe": (20, 27),
}


class PHQ9DatasetLoader(DatasetLoader):
    """Loader for PHQ-9 depression assessment data.
    
    Processes PHQ-9 scores into triage-labeled samples with
    generated text representations of symptom severity.
    """
    
    def __init__(
        self,
        config: Optional[PHQ9Config] = None,
        category_mapper: Optional[CategoryMapper] = None,
    ):
        super().__init__(config or PHQ9Config())
        self.mapper = category_mapper or CategoryMapper()
        self.thresholds = PHQ9Thresholds()
    
    def download(self) -> bool:
        """Download dataset from Kaggle or create synthetic data."""
        try:
            # Try Kaggle API
            try:
                import kaggle
                
                cache_path = self.config.cache_dir / "phq9_depression"
                cache_path.mkdir(parents=True, exist_ok=True)
                
                kaggle.api.dataset_download_files(
                    "thedevastator/phq-9-depression-assessment",
                    path=str(cache_path),
                    unzip=True,
                )
                
                logger.info("PHQ9_DOWNLOADED", extra={"path": str(cache_path)})
                return True
                
            except (ImportError, Exception) as e:
                logger.warning(f"Kaggle download failed: {e}. Creating synthetic data.")
                return self._create_synthetic_data()
                
        except Exception as e:
            logger.error("PHQ9_DOWNLOAD_ERROR", extra={"error": str(e)})
            return self._create_synthetic_data()

    def _create_synthetic_data(self) -> bool:
        """Create synthetic PHQ-9 data for testing."""
        cache_path = self.config.cache_dir / "phq9_depression"
        cache_path.mkdir(parents=True, exist_ok=True)
        
        import random
        random.seed(42)
        
        samples = []
        
        # Generate samples across severity spectrum
        for severity, (min_score, max_score) in PHQ9_SEVERITY.items():
            for i in range(50):  # 50 samples per severity level
                # Generate item scores that sum to target range
                total_target = random.randint(min_score, max_score)
                item_scores = self._generate_item_scores(total_target)
                
                samples.append({
                    "id": f"phq9_{severity}_{i}",
                    "item_scores": item_scores,
                    "total_score": sum(item_scores.values()),
                    "severity": severity,
                })
        
        # Save synthetic data
        with open(cache_path / "phq9_synthetic.json", "w") as f:
            json.dump(samples, f, indent=2)
        
        logger.info("PHQ9_SYNTHETIC_CREATED", extra={"samples": len(samples)})
        return True
    
    def _generate_item_scores(self, target_total: int) -> Dict[int, int]:
        """Generate item scores that sum to approximately the target."""
        import random
        
        scores = {i: 0 for i in range(1, 10)}
        
        if target_total == 0:
            return scores
        
        # Items 1-8 (excluding item 9 for now)
        items = list(range(1, 9))
        current_total = 0
        
        # Keep adding to scores until we reach target
        attempts = 0
        while current_total < target_total and attempts < 100:
            item = random.choice(items)
            if scores[item] < 3:  # Max score per item is 3
                scores[item] += 1
                current_total += 1
            attempts += 1
        
        # Item 9 (suicidal ideation) - special handling
        # Only positive if severe depression (score >= 20)
        if target_total >= 20 and random.random() < 0.5:
            scores[9] = random.randint(1, 3)
        elif target_total >= 15 and random.random() < 0.2:
            scores[9] = 1
        else:
            scores[9] = 0
        
        return scores
    
    def process(self) -> List[DatasetSample]:
        """Process PHQ-9 data into DatasetSamples."""
        samples = []
        cache_path = self.config.cache_dir / "phq9_depression"
        
        # Try to load real data first
        for csv_file in cache_path.glob("*.csv"):
            samples.extend(self._process_csv(csv_file))
        
        # Load synthetic data
        json_file = cache_path / "phq9_synthetic.json"
        if json_file.exists():
            samples.extend(self._process_synthetic(json_file))
        
        logger.info("PHQ9_PROCESSED", extra={"total_samples": len(samples)})
        return samples

    def _process_csv(self, csv_path: Path) -> List[DatasetSample]:
        """Process CSV file with PHQ-9 responses."""
        samples = []
        
        try:
            with open(csv_path, "r") as f:
                reader = csv.DictReader(f)
                for idx, row in enumerate(reader):
                    sample = self._process_row(row, idx)
                    if sample:
                        samples.append(sample)
        except Exception as e:
            logger.error("PHQ9_CSV_ERROR", extra={"file": str(csv_path), "error": str(e)})
        
        return samples
    
    def _process_synthetic(self, json_path: Path) -> List[DatasetSample]:
        """Process synthetic JSON data."""
        samples = []
        
        with open(json_path, "r") as f:
            data = json.load(f)
        
        for item in data:
            sample = self._create_sample_from_scores(
                sample_id=item["id"],
                item_scores=item["item_scores"],
                total_score=item["total_score"],
            )
            samples.append(sample)
        
        return samples
    
    def _process_row(self, row: Dict[str, Any], idx: int) -> Optional[DatasetSample]:
        """Process a single CSV row."""
        try:
            # Extract item scores (columns may vary by dataset)
            item_scores = {}
            total_score = 0
            
            for i in range(1, 10):
                # Try different column naming conventions
                for col_name in [f"q{i}", f"item{i}", f"phq{i}", f"Q{i}"]:
                    if col_name in row:
                        score = int(row[col_name])
                        item_scores[i] = score
                        total_score += score
                        break
            
            if not item_scores:
                # Try total score column
                for col_name in ["total", "score", "phq9_total", "total_score"]:
                    if col_name in row:
                        total_score = int(row[col_name])
                        break
            
            return self._create_sample_from_scores(
                sample_id=f"phq9_csv_{idx}",
                item_scores=item_scores,
                total_score=total_score,
            )
            
        except Exception as e:
            logger.warning("PHQ9_ROW_ERROR", extra={"idx": idx, "error": str(e)})
            return None

    def _create_sample_from_scores(
        self,
        sample_id: str,
        item_scores: Dict[int, int],
        total_score: int,
    ) -> DatasetSample:
        """Create a DatasetSample from PHQ-9 scores."""
        # Get item 9 score for crisis detection
        item9_score = item_scores.get(9, 0)
        
        # Map to triage level
        triage = self.mapper.map_phq9_to_triage(
            total_score=total_score,
            item9_score=item9_score,
        )
        
        # Generate text representation
        text = self._generate_text_from_scores(item_scores, total_score)
        
        # Determine severity category
        severity = self._get_severity_label(total_score)
        
        return DatasetSample(
            sample_id=sample_id,
            text=text,
            category="depression",
            triage_level=triage.value,
            severity_score=self.mapper.get_severity_from_phq9(total_score),
            source_dataset="phq9_depression",
            original_label=severity,
            phq9_score=total_score,
            metadata={
                "item_scores": item_scores,
                "item9_score": item9_score,
                "severity": severity,
            },
        )
    
    def _generate_text_from_scores(
        self,
        item_scores: Dict[int, int],
        total_score: int,
    ) -> str:
        """Generate natural language text from PHQ-9 scores."""
        statements = []
        
        # Collect statements for items with positive scores
        for item_num in sorted(item_scores.keys()):
            score = item_scores.get(item_num, 0)
            if score > 0 and item_num in PHQ9_ITEMS:
                item_text = PHQ9_ITEMS[item_num]
                
                if score == 3:
                    statements.append(f"I experience {item_text.lower()} nearly every day.")
                elif score == 2:
                    statements.append(f"I often have {item_text.lower()}.")
                elif score == 1:
                    statements.append(f"Sometimes I have {item_text.lower()}.")
        
        # Generate severity-appropriate text even if no specific items
        if not statements:
            # Generate text based on total score for minimal/mild cases
            if total_score >= 5:
                return "I've noticed I'm not feeling quite like myself lately. Some days are harder than others."
            else:
                return "I've been feeling okay lately. No major concerns."
        
        # Add severity context prefix
        if total_score >= 20:
            prefix = "I've been really struggling lately. "
        elif total_score >= 15:
            prefix = "Things have been very difficult for me. "
        elif total_score >= 10:
            prefix = "I've been having some challenges lately. "
        elif total_score >= 5:
            prefix = "I've noticed some changes in how I feel. "
        else:
            prefix = ""
        
        # Limit to 3 statements for readability
        text_statements = statements[:3]
        
        return prefix + " ".join(text_statements)
    
    def _get_severity_label(self, total_score: int) -> str:
        """Get severity label from total score."""
        for label, (min_s, max_s) in PHQ9_SEVERITY.items():
            if min_s <= total_score <= max_s:
                return label
        return "unknown"
    
    def get_by_severity(self, severity: str) -> List[DatasetSample]:
        """Get samples by severity level."""
        if not self._loaded:
            self.load()
        return [s for s in self._samples if s.metadata.get("severity") == severity]
    
    def get_crisis_samples(self) -> List[DatasetSample]:
        """Get samples with positive item 9 (suicidal ideation)."""
        if not self._loaded:
            self.load()
        return [s for s in self._samples if s.metadata.get("item9_score", 0) > 0]
