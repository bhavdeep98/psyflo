"""Benchmark loader and data structures.

Loads benchmark datasets from JSON files and provides
typed access to test cases.
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class BenchmarkCategory(Enum):
    """Categories of benchmark tests."""
    CRISIS_DETECTION = "crisis_detection"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    CLINICAL_MARKERS = "clinical_markers"
    ADVERSARIAL = "adversarial"
    FALSE_POSITIVE = "false_positive"
    LONGITUDINAL = "longitudinal"
    SESSION_PROGRESSION = "session_progression"


class ExpectedRiskLevel(Enum):
    """Expected risk level outcomes."""
    SAFE = "safe"
    CAUTION = "caution"
    CRISIS = "crisis"


@dataclass(frozen=True)
class BenchmarkCase:
    """Single benchmark test case.
    
    Immutable to ensure test integrity.
    """
    case_id: str
    category: BenchmarkCategory
    input_text: str
    expected_risk_level: ExpectedRiskLevel
    expected_bypass_llm: bool
    expected_keywords: List[str] = field(default_factory=list)
    description: str = ""
    source: str = ""  # e.g., "clinical_literature", "adversarial_research"
    severity_weight: float = 1.0  # Higher = more critical to catch
    
    # Optional session context for multi-message tests
    session_context: Optional[List[str]] = None
    expected_markers: Optional[List[str]] = None
    expected_phq9_range: Optional[tuple] = None
    expected_gad7_range: Optional[tuple] = None


@dataclass
class BenchmarkResult:
    """Result of running a benchmark case."""
    case_id: str
    passed: bool
    expected_risk_level: str
    actual_risk_level: str
    expected_bypass: bool
    actual_bypass: bool
    risk_score: float
    matched_keywords: List[str]
    latency_ms: float
    error: Optional[str] = None
    
    @property
    def is_false_negative(self) -> bool:
        """Crisis case that was missed."""
        return (
            self.expected_risk_level == "crisis" 
            and self.actual_risk_level != "crisis"
        )
    
    @property
    def is_false_positive(self) -> bool:
        """Safe case flagged as crisis."""
        return (
            self.expected_risk_level == "safe"
            and self.actual_risk_level == "crisis"
        )


@dataclass
class BenchmarkSuite:
    """Collection of benchmark cases."""
    name: str
    description: str
    cases: List[BenchmarkCase]
    version: str = "1.0.0"
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def crisis_cases(self) -> List[BenchmarkCase]:
        return [c for c in self.cases if c.expected_risk_level == ExpectedRiskLevel.CRISIS]
    
    @property
    def safe_cases(self) -> List[BenchmarkCase]:
        return [c for c in self.cases if c.expected_risk_level == ExpectedRiskLevel.SAFE]
    
    @property
    def caution_cases(self) -> List[BenchmarkCase]:
        return [c for c in self.cases if c.expected_risk_level == ExpectedRiskLevel.CAUTION]


class BenchmarkLoader:
    """Loads benchmark datasets from JSON files."""
    
    def __init__(self, benchmarks_dir: Optional[Path] = None):
        """Initialize loader.
        
        Args:
            benchmarks_dir: Directory containing benchmark JSON files.
                           Defaults to this module's directory.
        """
        if benchmarks_dir is None:
            benchmarks_dir = Path(__file__).parent
        self.benchmarks_dir = benchmarks_dir
        self._cache: Dict[str, BenchmarkSuite] = {}
        
        logger.info(
            "BENCHMARK_LOADER_INITIALIZED",
            extra={"benchmarks_dir": str(benchmarks_dir)}
        )
    
    def load_suite(self, name: str) -> BenchmarkSuite:
        """Load a benchmark suite by name.
        
        Args:
            name: Name of the benchmark file (without .json extension)
            
        Returns:
            BenchmarkSuite with all test cases
            
        Raises:
            FileNotFoundError: If benchmark file doesn't exist
            ValueError: If benchmark file is malformed
        """
        if name in self._cache:
            return self._cache[name]
        
        file_path = self.benchmarks_dir / f"{name}.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Benchmark file not found: {file_path}")
        
        with open(file_path, "r") as f:
            data = json.load(f)
        
        cases = []
        for case_data in data.get("cases", []):
            case = BenchmarkCase(
                case_id=case_data["case_id"],
                category=BenchmarkCategory(case_data["category"]),
                input_text=case_data["input_text"],
                expected_risk_level=ExpectedRiskLevel(case_data["expected_risk_level"]),
                expected_bypass_llm=case_data.get("expected_bypass_llm", False),
                expected_keywords=case_data.get("expected_keywords", []),
                description=case_data.get("description", ""),
                source=case_data.get("source", ""),
                severity_weight=case_data.get("severity_weight", 1.0),
                session_context=case_data.get("session_context"),
                expected_markers=case_data.get("expected_markers"),
                expected_phq9_range=tuple(case_data["expected_phq9_range"]) if case_data.get("expected_phq9_range") else None,
                expected_gad7_range=tuple(case_data["expected_gad7_range"]) if case_data.get("expected_gad7_range") else None,
            )
            cases.append(case)
        
        suite = BenchmarkSuite(
            name=data.get("name", name),
            description=data.get("description", ""),
            cases=cases,
            version=data.get("version", "1.0.0"),
        )
        
        self._cache[name] = suite
        
        logger.info(
            "BENCHMARK_SUITE_LOADED",
            extra={
                "suite_name": name,
                "case_count": len(cases),
                "crisis_count": len(suite.crisis_cases),
                "safe_count": len(suite.safe_cases),
            }
        )
        
        return suite
    
    def load_all(self) -> Dict[str, BenchmarkSuite]:
        """Load all benchmark suites in the directory.
        
        Returns:
            Dictionary mapping suite names to BenchmarkSuite objects
        """
        suites = {}
        for file_path in self.benchmarks_dir.glob("*.json"):
            name = file_path.stem
            try:
                suites[name] = self.load_suite(name)
            except Exception as e:
                logger.error(
                    "BENCHMARK_LOAD_ERROR",
                    extra={"file": str(file_path), "error": str(e)}
                )
        return suites
    
    def get_all_cases(self) -> List[BenchmarkCase]:
        """Get all cases from all suites.
        
        Returns:
            Flat list of all benchmark cases
        """
        all_cases = []
        for suite in self.load_all().values():
            all_cases.extend(suite.cases)
        return all_cases
    
    def get_cases_by_category(self, category: BenchmarkCategory) -> List[BenchmarkCase]:
        """Get all cases of a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of matching benchmark cases
        """
        return [c for c in self.get_all_cases() if c.category == category]
