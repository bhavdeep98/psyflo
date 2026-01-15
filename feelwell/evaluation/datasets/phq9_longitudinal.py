"""PHQ-9 Longitudinal Dataset Loader.

Loads real PHQ-9 time-series data for testing longitudinal triage.
Dataset: Kaggle PHQ-9 Depression Mood Dynamics
Source: https://www.kaggle.com/code/stpeteishii/phq-9-depression-predict-and-visualize-importance

Dataset contains daily PHQ-9 scores over 14+ days for mood dynamics analysis.

Columns:
- phq1-phq9: Daily PHQ-9 scores (days 1-9)
- q10-q14, q16, q46, q47: Additional day scores
- age, sex: Demographics
- happiness.score: Happiness metric
- time, period.name, start.time, phq.day: Temporal metadata

Usage:
    # With local CSV file
    loader = PHQ9LongitudinalLoader(PHQ9LongitudinalConfig(data_path="path/to/phq9.csv"))
    samples = loader.load()
    
    # Convert to StudentHistory for triage evaluation
    histories = loader.to_student_histories(samples)
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path
import statistics

from feelwell.shared.utils import hash_pii
from ..triage.longitudinal_triage import (
    StudentHistory,
    LongitudinalPattern,
)

logger = logging.getLogger(__name__)


@dataclass
class PHQ9LongitudinalConfig:
    """Configuration for PHQ-9 longitudinal dataset loading."""
    data_path: Optional[str] = None
    max_samples: int = 100
    min_days: int = 7  # Minimum days of data required
    normalize_scores: bool = True  # Normalize to 0-1 range


@dataclass
class PHQ9TimeSeriesSample:
    """A single participant's PHQ-9 time series."""
    participant_id: str
    daily_scores: List[float]  # PHQ-9 scores per day
    days: List[int]  # Day numbers
    age: Optional[int] = None
    sex: Optional[str] = None
    happiness_score: Optional[float] = None
    inferred_pattern: Optional[LongitudinalPattern] = None
    
    @property
    def duration_days(self) -> int:
        return max(self.days) - min(self.days) + 1 if self.days else 0
    
    @property
    def avg_score(self) -> float:
        return statistics.mean(self.daily_scores) if self.daily_scores else 0.0
    
    @property
    def score_variance(self) -> float:
        return statistics.variance(self.daily_scores) if len(self.daily_scores) > 1 else 0.0
    
    @property
    def trend_slope(self) -> float:
        """Calculate linear trend slope."""
        if len(self.daily_scores) < 2:
            return 0.0
        n = len(self.daily_scores)
        x_mean = sum(self.days) / n
        y_mean = self.avg_score
        
        numerator = sum((self.days[i] - x_mean) * (self.daily_scores[i] - y_mean) for i in range(n))
        denominator = sum((self.days[i] - x_mean) ** 2 for i in range(n))
        
        return numerator / denominator if denominator != 0 else 0.0


class PHQ9LongitudinalLoader:
    """Loader for PHQ-9 longitudinal time-series data.
    
    Converts raw PHQ-9 daily scores into StudentHistory objects
    for longitudinal triage evaluation.
    
    Dataset source: Kaggle PHQ-9 Depression Mood Dynamics
    """
    
    # PHQ-9 score thresholds (standard clinical cutoffs)
    MINIMAL = 4
    MILD = 9
    MODERATE = 14
    MODERATELY_SEVERE = 19
    SEVERE = 27  # Max is 27
    
    # Kaggle dataset info
    KAGGLE_DATASET = "stpeteishii/phq-9-depression-predict-and-visualize-importance"
    
    def __init__(self, config: Optional[PHQ9LongitudinalConfig] = None):
        self.config = config or PHQ9LongitudinalConfig()
        logger.info("PHQ9_LONGITUDINAL_LOADER_INITIALIZED", extra={
            "max_samples": self.config.max_samples,
        })
    
    def load(self) -> List[PHQ9TimeSeriesSample]:
        """Load PHQ-9 longitudinal samples.
        
        Returns:
            List of PHQ9TimeSeriesSample objects
        """
        # Try to load from file if path provided
        if self.config.data_path:
            return self._load_from_file(self.config.data_path)
        
        # Try to find cached dataset
        cache_path = self._get_cache_path()
        if cache_path.exists():
            logger.info(f"Loading from cache: {cache_path}")
            return self._load_from_file(str(cache_path))
        
        # Try Kaggle API
        try:
            return self._load_from_kaggle()
        except Exception as e:
            logger.warning(f"Kaggle load failed: {e}")
        
        # Fall back to synthetic data
        logger.info("Using synthetic PHQ-9 longitudinal data")
        return self._generate_synthetic_samples()
    
    def _get_cache_path(self) -> Path:
        """Get path for cached dataset."""
        cache_dir = Path(__file__).parent / "cache"
        cache_dir.mkdir(exist_ok=True)
        return cache_dir / "phq9_longitudinal.csv"
    
    def _load_from_kaggle(self) -> List[PHQ9TimeSeriesSample]:
        """Download and load from Kaggle."""
        try:
            import kaggle
            
            cache_dir = Path(__file__).parent / "cache"
            cache_dir.mkdir(exist_ok=True)
            
            # Download dataset
            kaggle.api.dataset_download_files(
                self.KAGGLE_DATASET,
                path=str(cache_dir),
                unzip=True,
            )
            
            # Find CSV file
            csv_files = list(cache_dir.glob("*.csv"))
            if csv_files:
                return self._load_from_file(str(csv_files[0]))
            
            raise FileNotFoundError("No CSV found in Kaggle download")
            
        except ImportError:
            raise ImportError(
                "Kaggle API not installed. Install with: pip install kaggle\n"
                "Then configure credentials: https://www.kaggle.com/docs/api"
            )
    
    def _load_from_file(self, path: str) -> List[PHQ9TimeSeriesSample]:
        """Load from CSV file."""
        import csv
        
        samples = []
        file_path = Path(path)
        
        if not file_path.exists():
            logger.warning(f"File not found: {path}")
            return self._generate_synthetic_samples()
        
        with open(file_path, 'r') as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                if idx >= self.config.max_samples:
                    break
                
                sample = self._parse_row(row, idx)
                if sample and len(sample.daily_scores) >= self.config.min_days:
                    samples.append(sample)
        
        logger.info(f"Loaded {len(samples)} samples from {path}")
        return samples
    
    def _parse_row(self, row: Dict[str, Any], idx: int) -> Optional[PHQ9TimeSeriesSample]:
        """Parse a single row into PHQ9TimeSeriesSample."""
        daily_scores = []
        days = []
        
        # Map column names to day numbers
        day_columns = {
            'phq1': 1, 'phq2': 2, 'phq3': 3, 'phq4': 4, 'phq5': 5,
            'phq6': 6, 'phq7': 7, 'phq8': 8, 'phq9': 9,
            'q10': 10, 'q11': 11, 'q12': 12, 'q13': 13, 'q14': 14,
            'q16': 16, 'q46': 46, 'q47': 47,
        }
        
        for col, day in day_columns.items():
            if col in row and row[col] is not None:
                try:
                    score = float(row[col])
                    if self.config.normalize_scores:
                        score = score / 27.0  # Normalize to 0-1
                    daily_scores.append(score)
                    days.append(day)
                except (ValueError, TypeError):
                    continue
        
        if len(daily_scores) < self.config.min_days:
            return None
        
        # Extract demographics
        age = None
        if 'age' in row:
            try:
                age = int(row['age'])
            except (ValueError, TypeError):
                pass
        
        sex = row.get('sex')
        
        happiness = None
        if 'happiness.score' in row or 'happiness_score' in row:
            try:
                happiness = float(row.get('happiness.score') or row.get('happiness_score'))
            except (ValueError, TypeError):
                pass
        
        sample = PHQ9TimeSeriesSample(
            participant_id=f"phq9_long_{idx}",
            daily_scores=daily_scores,
            days=days,
            age=age,
            sex=sex,
            happiness_score=happiness,
        )
        
        # Infer pattern from data
        sample.inferred_pattern = self._infer_pattern(sample)
        
        return sample
    
    def _infer_pattern(self, sample: PHQ9TimeSeriesSample) -> LongitudinalPattern:
        """Infer longitudinal pattern from PHQ-9 time series.
        
        Uses clinical thresholds and trend analysis.
        """
        avg = sample.avg_score
        variance = sample.score_variance
        slope = sample.trend_slope
        
        # Normalize thresholds if scores are normalized
        if self.config.normalize_scores:
            minimal_thresh = self.MINIMAL / 27.0
            mild_thresh = self.MILD / 27.0
            moderate_thresh = self.MODERATE / 27.0
        else:
            minimal_thresh = self.MINIMAL
            mild_thresh = self.MILD
            moderate_thresh = self.MODERATE
        
        # Check for acute crisis (sudden spike)
        if len(sample.daily_scores) >= 3:
            max_score = max(sample.daily_scores)
            if max_score > moderate_thresh and sample.daily_scores[-1] > moderate_thresh:
                recent_jump = sample.daily_scores[-1] - statistics.mean(sample.daily_scores[:-1])
                if recent_jump > 0.2:  # Significant recent increase
                    return LongitudinalPattern.ACUTE_CRISIS
        
        # Check for gradual decline (worsening)
        if slope > 0.01:  # Positive slope = increasing scores = worsening
            if avg > mild_thresh:
                return LongitudinalPattern.GRADUAL_DECLINE
        
        # Check for recovery (improving)
        if slope < -0.01:  # Negative slope = decreasing scores = improving
            return LongitudinalPattern.RECOVERY
        
        # Check for cyclical pattern (high variance, no clear trend)
        if variance > 0.02 and abs(slope) < 0.005:
            return LongitudinalPattern.CYCLICAL
        
        # Check for chronic low (persistent moderate symptoms)
        if mild_thresh <= avg <= moderate_thresh and variance < 0.01:
            return LongitudinalPattern.CHRONIC_LOW
        
        # Check for stable healthy
        if avg < minimal_thresh:
            return LongitudinalPattern.STABLE_HEALTHY
        
        # Default to chronic low for moderate persistent symptoms
        if avg >= mild_thresh:
            return LongitudinalPattern.CHRONIC_LOW
        
        return LongitudinalPattern.STABLE_HEALTHY
    
    def _generate_synthetic_samples(self) -> List[PHQ9TimeSeriesSample]:
        """Generate synthetic PHQ-9 longitudinal samples for testing."""
        import random
        
        samples = []
        patterns = list(LongitudinalPattern)
        
        for idx in range(self.config.max_samples):
            pattern = patterns[idx % len(patterns)]
            sample = self._generate_sample_for_pattern(pattern, idx)
            samples.append(sample)
        
        logger.info(f"Generated {len(samples)} synthetic PHQ-9 longitudinal samples")
        return samples
    
    def _generate_sample_for_pattern(
        self,
        pattern: LongitudinalPattern,
        idx: int,
    ) -> PHQ9TimeSeriesSample:
        """Generate a synthetic sample matching a specific pattern."""
        import random
        import math
        
        # Generate 14 days of data
        days = list(range(1, 15))
        daily_scores = []
        
        for day in days:
            progress = day / 14.0
            
            if pattern == LongitudinalPattern.STABLE_HEALTHY:
                base = 0.1 + random.uniform(-0.05, 0.05)
            
            elif pattern == LongitudinalPattern.CHRONIC_LOW:
                base = 0.35 + random.uniform(-0.05, 0.05)
            
            elif pattern == LongitudinalPattern.GRADUAL_DECLINE:
                base = 0.2 + (0.5 * progress) + random.uniform(-0.05, 0.05)
            
            elif pattern == LongitudinalPattern.ACUTE_CRISIS:
                if progress > 0.7:
                    base = 0.8 + random.uniform(0, 0.15)
                else:
                    base = 0.25 + random.uniform(-0.05, 0.05)
            
            elif pattern == LongitudinalPattern.CYCLICAL:
                base = 0.35 + 0.2 * math.sin(progress * 3 * math.pi) + random.uniform(-0.05, 0.05)
            
            elif pattern == LongitudinalPattern.RECOVERY:
                base = 0.6 - (0.4 * progress) + random.uniform(-0.05, 0.05)
            
            elif pattern == LongitudinalPattern.SEASONAL:
                # Simulate weekly pattern
                base = 0.3 + (0.2 if day % 7 < 3 else 0) + random.uniform(-0.05, 0.05)
            
            else:
                base = 0.3 + random.uniform(-0.1, 0.1)
            
            daily_scores.append(max(0, min(1, base)))
        
        return PHQ9TimeSeriesSample(
            participant_id=f"phq9_synth_{idx}",
            daily_scores=daily_scores,
            days=days,
            age=random.randint(18, 65),
            sex=random.choice(['M', 'F']),
            happiness_score=1.0 - statistics.mean(daily_scores),  # Inverse correlation
            inferred_pattern=pattern,
        )
    
    def to_student_histories(
        self,
        samples: List[PHQ9TimeSeriesSample],
    ) -> List[StudentHistory]:
        """Convert PHQ-9 samples to StudentHistory for triage evaluation.
        
        Args:
            samples: List of PHQ9TimeSeriesSample
            
        Returns:
            List of StudentHistory objects
        """
        histories = []
        
        for sample in samples:
            # Convert daily scores to risk trajectory
            risk_trajectory = sample.daily_scores
            
            # Create session data from daily scores
            base_time = datetime.utcnow() - timedelta(days=sample.duration_days)
            sessions = []
            crisis_count = 0
            
            for i, (day, score) in enumerate(zip(sample.days, sample.daily_scores)):
                session_time = base_time + timedelta(days=day)
                
                # Count crisis events (high scores)
                if score > 0.7:
                    crisis_count += 1
                
                sessions.append({
                    "session_id": f"sess_{sample.participant_id}_{i}",
                    "timestamp": session_time,
                    "risk_score": score,
                    "message_count": 5,  # Placeholder
                    "phq9_score": int(score * 27),
                    "counselor_flag": score > 0.5,
                })
            
            history = StudentHistory(
                student_id_hash=hash_pii(sample.participant_id),
                sessions=sessions,
                first_session=base_time,
                last_session=sessions[-1]["timestamp"] if sessions else base_time,
                total_messages=len(sessions) * 5,
                crisis_count=crisis_count,
                avg_risk_score=sample.avg_score,
                risk_trajectory=risk_trajectory,
                known_pattern=sample.inferred_pattern,
            )
            
            histories.append(history)
        
        return histories
