"""Safety scanner implementation - Multi-layer defense.

This module implements the deterministic guardrails per ADR-001.
All scanning happens BEFORE the LLM sees any message.

Architecture:
- Layer 1: Keyword matching (fastest, catches explicit language)
- Layer 2: Semantic analysis (PHQ-9/GAD-7 clinical markers)
- Combined: Weighted risk score with full explainability
"""
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from feelwell.shared.models import RiskLevel
from feelwell.shared.utils import hash_pii, hash_text_for_audit
from .config import (
    CRISIS_KEYWORDS,
    CAUTION_KEYWORDS,
    ClinicalThresholds,
    SafetyConfig,
)
from .semantic_analyzer import SemanticAnalyzer, SemanticAnalysisResult
from .text_normalizer import TextNormalizer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanResult:
    """Result of safety scan on a message.
    
    Immutable - scan results cannot be modified after creation.
    Includes both keyword-based and semantic analysis results.
    """
    message_id: str
    risk_level: RiskLevel
    risk_score: float
    bypass_llm: bool
    matched_keywords: List[str] = field(default_factory=list)
    scan_latency_ms: float = 0.0
    scanner_version: str = ""
    scanned_at: datetime = field(default_factory=datetime.utcnow)
    # Layer 2: Semantic analysis results
    semantic_analysis: Optional[SemanticAnalysisResult] = None
    # Combined scoring breakdown
    keyword_risk_score: float = 0.0
    semantic_risk_score: float = 0.0
    
    def __post_init__(self):
        if not 0.0 <= self.risk_score <= 1.0:
            raise ValueError(f"Risk score must be 0.0-1.0, got {self.risk_score}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = {
            "message_id": self.message_id,
            "risk_level": self.risk_level.value,
            "risk_score": round(self.risk_score, 3),
            "bypass_llm": self.bypass_llm,
            "matched_keywords": self.matched_keywords,
            "scan_latency_ms": round(self.scan_latency_ms, 2),
            "scanner_version": self.scanner_version,
            "scanned_at": self.scanned_at.isoformat(),
            "keyword_risk_score": round(self.keyword_risk_score, 3),
            "semantic_risk_score": round(self.semantic_risk_score, 3),
        }
        if self.semantic_analysis:
            result["semantic_analysis"] = self.semantic_analysis.to_dict()
        return result


class SafetyScanner:
    """Deterministic safety scanner for student messages.
    
    Implements layered defense:
    1. Regex keyword matching (fastest, catches explicit language)
    2. Semantic analysis (PHQ-9/GAD-7 clinical markers)
    3. Combined weighted scoring with full explainability
    
    Per ADR-001: If CRISIS detected, LLM is bypassed entirely.
    """
    
    # Weights for combining layer scores
    KEYWORD_WEIGHT = 0.6  # Layer 1 - explicit keywords
    SEMANTIC_WEIGHT = 0.4  # Layer 2 - clinical patterns
    
    def __init__(
        self,
        config: Optional[SafetyConfig] = None,
        thresholds: Optional[ClinicalThresholds] = None,
        enable_semantic: bool = True,
    ):
        """Initialize scanner with configuration.
        
        Args:
            config: Scanner behavior configuration
            thresholds: Clinical severity thresholds
            enable_semantic: Whether to run semantic analysis (Layer 2)
        """
        self.config = config or SafetyConfig()
        self.thresholds = thresholds or ClinicalThresholds()
        self.enable_semantic = enable_semantic
        
        # Pre-compile regex patterns for performance
        self._crisis_patterns = self._compile_patterns(CRISIS_KEYWORDS)
        self._caution_patterns = self._compile_patterns(CAUTION_KEYWORDS)
        
        # Initialize text normalizer for adversarial evasion detection
        self._text_normalizer = TextNormalizer()
        
        # Initialize semantic analyzer
        self._semantic_analyzer: Optional[SemanticAnalyzer] = None
        if enable_semantic:
            self._semantic_analyzer = SemanticAnalyzer()
        
        logger.info(
            "SAFETY_SCANNER_INITIALIZED",
            extra={
                "pattern_version": self.config.pattern_version,
                "crisis_pattern_count": len(CRISIS_KEYWORDS),
                "caution_pattern_count": len(CAUTION_KEYWORDS),
                "semantic_enabled": enable_semantic,
                "text_normalization_enabled": True,
            }
        )
    
    def _compile_patterns(self, keywords: Set[str]) -> List[re.Pattern]:
        """Compile keywords into regex patterns with word boundaries.
        
        Args:
            keywords: Set of keywords to compile
            
        Returns:
            List of compiled regex patterns
        """
        patterns = []
        for keyword in keywords:
            # Word boundaries prevent partial matches
            # e.g., "cut" won't match "cute"
            pattern = re.compile(
                rf"\b{re.escape(keyword)}\b",
                re.IGNORECASE
            )
            patterns.append(pattern)
        return patterns
    
    def scan(self, message_id: str, text: str, student_id: str) -> ScanResult:
        """Scan a message for safety concerns.
        
        This is the main entry point. Every student message MUST pass
        through this method before reaching the LLM.
        
        Args:
            message_id: Unique identifier for the message
            text: Raw message text from student
            student_id: Student identifier (will be hashed for logging)
            
        Returns:
            ScanResult with risk assessment and bypass decision
            
        Logs:
            - SAFETY_SCAN_STARTED: Before scan begins
            - SAFETY_SCAN_CRISIS: If crisis detected (critical level)
            - SAFETY_SCAN_CAUTION: If caution keywords found
            - SAFETY_SCAN_COMPLETED: After scan finishes
        """
        start_time = time.perf_counter()
        student_id_hash = hash_pii(student_id)
        text_hash = hash_text_for_audit(text)
        
        logger.info(
            "SAFETY_SCAN_STARTED",
            extra={
                "message_id": message_id,
                "student_id_hash": student_id_hash,
                "text_hash": text_hash,
                "text_length": len(text),
            }
        )
        
        # Normalize text for matching - handles evasion techniques
        # Step 1: Basic normalization (lowercase, strip)
        normalized_text = text.lower().strip()
        
        # Step 2: Advanced normalization (leetspeak, unicode, separators)
        # This catches adversarial attempts like K1LL, k.i.l.l, ⓚⓘⓛⓛ
        adversarial_normalized = self._text_normalizer.normalize(text)
        
        # Layer 1: Crisis keyword scan on BOTH normalizations (highest priority)
        crisis_matches = self._scan_patterns(normalized_text, self._crisis_patterns)
        if not crisis_matches:
            # Try adversarial-normalized text if basic didn't match
            crisis_matches = self._scan_patterns(adversarial_normalized, self._crisis_patterns)
        if crisis_matches:
            return self._create_crisis_result(
                message_id=message_id,
                matched_keywords=crisis_matches,
                start_time=start_time,
                student_id_hash=student_id_hash,
                text=normalized_text,
            )
        
        # Layer 1 continued: Caution keyword scan (both normalizations)
        caution_matches = self._scan_patterns(normalized_text, self._caution_patterns)
        if not caution_matches:
            caution_matches = self._scan_patterns(adversarial_normalized, self._caution_patterns)
        keyword_risk_score = self._calculate_keyword_risk_score(caution_matches)
        
        # Layer 2: Semantic analysis (clinical markers)
        semantic_result: Optional[SemanticAnalysisResult] = None
        semantic_risk_score = 0.0
        
        if self._semantic_analyzer:
            semantic_result = self._semantic_analyzer.analyze(text)
            semantic_risk_score = semantic_result.semantic_risk_score
            
            # Check for critical markers (suicidal ideation via semantic patterns)
            if semantic_result.has_critical_markers():
                return self._create_crisis_result(
                    message_id=message_id,
                    matched_keywords=caution_matches,
                    start_time=start_time,
                    student_id_hash=student_id_hash,
                    text=normalized_text,
                    semantic_result=semantic_result,
                )
        
        # Combine scores from both layers
        combined_risk_score = self._combine_risk_scores(
            keyword_score=keyword_risk_score,
            semantic_score=semantic_risk_score,
        )
        risk_level = self._determine_risk_level(combined_risk_score)
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        if caution_matches or (semantic_result and semantic_result.markers):
            logger.warning(
                "SAFETY_SCAN_CAUTION",
                extra={
                    "message_id": message_id,
                    "student_id_hash": student_id_hash,
                    "keyword_matches": len(caution_matches),
                    "semantic_markers": len(semantic_result.markers) if semantic_result else 0,
                    "keyword_risk": keyword_risk_score,
                    "semantic_risk": semantic_risk_score,
                    "combined_risk": combined_risk_score,
                    "latency_ms": latency_ms,
                }
            )
        
        result = ScanResult(
            message_id=message_id,
            risk_level=risk_level,
            risk_score=combined_risk_score,
            bypass_llm=False,
            matched_keywords=caution_matches,
            scan_latency_ms=latency_ms,
            scanner_version=self.config.pattern_version,
            semantic_analysis=semantic_result,
            keyword_risk_score=keyword_risk_score,
            semantic_risk_score=semantic_risk_score,
        )
        
        logger.info(
            "SAFETY_SCAN_COMPLETED",
            extra={
                "message_id": message_id,
                "student_id_hash": student_id_hash,
                "risk_level": risk_level.value,
                "combined_risk": combined_risk_score,
                "keyword_risk": keyword_risk_score,
                "semantic_risk": semantic_risk_score,
                "bypass_llm": False,
                "latency_ms": latency_ms,
            }
        )
        
        return result
    
    def _scan_patterns(
        self, 
        text: str, 
        patterns: List[re.Pattern]
    ) -> List[str]:
        """Scan text against compiled patterns.
        
        Args:
            text: Normalized text to scan
            patterns: Compiled regex patterns
            
        Returns:
            List of matched keyword strings
        """
        matches = []
        for pattern in patterns:
            if pattern.search(text):
                # Extract the original keyword from pattern
                matches.append(pattern.pattern.replace(r"\b", ""))
        return matches
    
    def _calculate_keyword_risk_score(self, caution_matches: List[str]) -> float:
        """Calculate risk score based on caution keyword matches.
        
        Args:
            caution_matches: List of matched caution keywords
            
        Returns:
            Risk score between 0.0 and 1.0
        """
        if not caution_matches:
            return 0.1  # Baseline score for any message
        
        # Each caution keyword adds to risk score
        # Diminishing returns after 3 matches
        match_count = len(caution_matches)
        if match_count == 1:
            return 0.4
        elif match_count == 2:
            return 0.5
        elif match_count >= 3:
            return min(0.7, 0.5 + (match_count - 2) * 0.05)
        
        return 0.1
    
    def _combine_risk_scores(
        self,
        keyword_score: float,
        semantic_score: float,
    ) -> float:
        """Combine keyword and semantic risk scores.
        
        Uses weighted average with boost for agreement between layers.
        
        Args:
            keyword_score: Risk score from keyword matching (0-1)
            semantic_score: Risk score from semantic analysis (0-1)
            
        Returns:
            Combined risk score (0-1)
        """
        # Weighted combination
        base_score = (
            keyword_score * self.KEYWORD_WEIGHT +
            semantic_score * self.SEMANTIC_WEIGHT
        )
        
        # Boost if both layers agree on elevated risk
        if keyword_score >= 0.4 and semantic_score >= 0.4:
            agreement_boost = 0.1
            base_score = min(1.0, base_score + agreement_boost)
        
        # If semantic analysis found critical markers, ensure minimum score
        if semantic_score >= 0.9:
            base_score = max(base_score, 0.7)
        
        return min(1.0, base_score)
    
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Map risk score to risk level enum.
        
        Args:
            risk_score: Calculated risk score
            
        Returns:
            Appropriate RiskLevel enum value
        """
        if risk_score <= self.thresholds.LOW_SEVERITY_MAX:
            return RiskLevel.SAFE
        elif risk_score <= self.thresholds.MODERATE_SEVERITY_MAX:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.CRISIS
    
    def _create_crisis_result(
        self,
        message_id: str,
        matched_keywords: List[str],
        start_time: float,
        student_id_hash: str,
        text: str,
        semantic_result: Optional[SemanticAnalysisResult] = None,
    ) -> ScanResult:
        """Create a crisis-level scan result with LLM bypass.
        
        Per ADR-001: Crisis detection triggers immediate bypass.
        The LLM never sees this message.
        
        Args:
            message_id: Message identifier
            matched_keywords: Crisis keywords that were matched
            start_time: Scan start time for latency calculation
            student_id_hash: Hashed student ID for logging
            text: Normalized text (for semantic analysis if not done)
            semantic_result: Pre-computed semantic result (if available)
            
        Returns:
            ScanResult with bypass_llm=True
        """
        # Run semantic analysis if not already done (for full context)
        if semantic_result is None and self._semantic_analyzer:
            semantic_result = self._semantic_analyzer.analyze(text)
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        logger.critical(
            "SAFETY_SCAN_CRISIS",
            extra={
                "message_id": message_id,
                "student_id_hash": student_id_hash,
                "keyword_matches": len(matched_keywords),
                "semantic_critical": semantic_result.has_critical_markers() if semantic_result else False,
                "bypass_llm": True,
                "latency_ms": latency_ms,
                "action": "CRISIS_ENGINE_TRIGGERED",
            }
        )
        
        return ScanResult(
            message_id=message_id,
            risk_level=RiskLevel.CRISIS,
            risk_score=1.0,
            bypass_llm=True,
            matched_keywords=matched_keywords,
            scan_latency_ms=latency_ms,
            scanner_version=self.config.pattern_version,
            semantic_analysis=semantic_result,
            keyword_risk_score=1.0,
            semantic_risk_score=semantic_result.semantic_risk_score if semantic_result else 0.0,
        )
