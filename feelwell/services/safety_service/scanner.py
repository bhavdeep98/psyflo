"""Safety scanner implementation - Layer 1 defense.

This module implements the deterministic guardrails per ADR-001.
All scanning happens BEFORE the LLM sees any message.
"""
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Set

from feelwell.shared.models import RiskLevel
from feelwell.shared.utils import hash_pii, hash_text_for_audit
from .config import (
    CRISIS_KEYWORDS,
    CAUTION_KEYWORDS,
    ClinicalThresholds,
    SafetyConfig,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScanResult:
    """Result of safety scan on a message.
    
    Immutable - scan results cannot be modified after creation.
    """
    message_id: str
    risk_level: RiskLevel
    risk_score: float
    bypass_llm: bool
    matched_keywords: List[str] = field(default_factory=list)
    scan_latency_ms: float = 0.0
    scanner_version: str = ""
    scanned_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if not 0.0 <= self.risk_score <= 1.0:
            raise ValueError(f"Risk score must be 0.0-1.0, got {self.risk_score}")


class SafetyScanner:
    """Deterministic safety scanner for student messages.
    
    Implements layered defense:
    1. Regex keyword matching (fastest, catches explicit language)
    2. Pattern matching for coded language
    3. BERT sentiment pre-scan (if enabled)
    
    Per ADR-001: If CRISIS detected, LLM is bypassed entirely.
    """
    
    def __init__(
        self,
        config: Optional[SafetyConfig] = None,
        thresholds: Optional[ClinicalThresholds] = None,
    ):
        """Initialize scanner with configuration.
        
        Args:
            config: Scanner behavior configuration
            thresholds: Clinical severity thresholds
        """
        self.config = config or SafetyConfig()
        self.thresholds = thresholds or ClinicalThresholds()
        
        # Pre-compile regex patterns for performance
        self._crisis_patterns = self._compile_patterns(CRISIS_KEYWORDS)
        self._caution_patterns = self._compile_patterns(CAUTION_KEYWORDS)
        
        logger.info(
            "SAFETY_SCANNER_INITIALIZED",
            extra={
                "pattern_version": self.config.pattern_version,
                "crisis_pattern_count": len(CRISIS_KEYWORDS),
                "caution_pattern_count": len(CAUTION_KEYWORDS),
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
        
        # Normalize text for matching
        normalized_text = text.lower().strip()
        
        # Layer 1: Crisis keyword scan (highest priority)
        crisis_matches = self._scan_patterns(normalized_text, self._crisis_patterns)
        if crisis_matches:
            return self._create_crisis_result(
                message_id=message_id,
                matched_keywords=crisis_matches,
                start_time=start_time,
                student_id_hash=student_id_hash,
            )
        
        # Layer 2: Caution keyword scan
        caution_matches = self._scan_patterns(normalized_text, self._caution_patterns)
        risk_score = self._calculate_risk_score(caution_matches)
        risk_level = self._determine_risk_level(risk_score)
        
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        if caution_matches:
            logger.warning(
                "SAFETY_SCAN_CAUTION",
                extra={
                    "message_id": message_id,
                    "student_id_hash": student_id_hash,
                    "match_count": len(caution_matches),
                    "risk_score": risk_score,
                    "latency_ms": latency_ms,
                }
            )
        
        result = ScanResult(
            message_id=message_id,
            risk_level=risk_level,
            risk_score=risk_score,
            bypass_llm=False,
            matched_keywords=caution_matches,
            scan_latency_ms=latency_ms,
            scanner_version=self.config.pattern_version,
        )
        
        logger.info(
            "SAFETY_SCAN_COMPLETED",
            extra={
                "message_id": message_id,
                "student_id_hash": student_id_hash,
                "risk_level": risk_level.value,
                "risk_score": risk_score,
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
    
    def _calculate_risk_score(self, caution_matches: List[str]) -> float:
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
            return min(0.6, 0.5 + (match_count - 2) * 0.05)
        
        return 0.1
    
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
    ) -> ScanResult:
        """Create a crisis-level scan result with LLM bypass.
        
        Per ADR-001: Crisis detection triggers immediate bypass.
        The LLM never sees this message.
        
        Args:
            message_id: Message identifier
            matched_keywords: Crisis keywords that were matched
            start_time: Scan start time for latency calculation
            student_id_hash: Hashed student ID for logging
            
        Returns:
            ScanResult with bypass_llm=True
        """
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        logger.critical(
            "SAFETY_SCAN_CRISIS",
            extra={
                "message_id": message_id,
                "student_id_hash": student_id_hash,
                "match_count": len(matched_keywords),
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
        )
