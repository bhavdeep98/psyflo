"""Safety Service configuration and clinical thresholds.

Source: PHQ-9 scoring guidelines
https://www.apa.org/depression-guideline/patient-health-questionnaire.pdf
"""
from dataclasses import dataclass
from typing import FrozenSet


@dataclass(frozen=True)
class ClinicalThresholds:
    """Clinical severity thresholds based on PHQ-9 scoring guidelines.
    
    These thresholds determine when to escalate to human intervention.
    """
    LOW_SEVERITY_MAX: float = 0.3       # Score 0-4: Self-help appropriate
    MODERATE_SEVERITY_MAX: float = 0.6  # Score 5-9: Counselor suggested
    HIGH_SEVERITY_MIN: float = 0.7      # Score 10+: Immediate intervention
    CRISIS_THRESHOLD: float = 0.85      # Any red flag: Kill switch activated


@dataclass(frozen=True)
class SafetyConfig:
    """Configuration for safety scanning behavior."""
    
    # Minimum confidence to flag a crisis keyword match
    crisis_keyword_confidence: float = 0.9
    
    # Maximum latency allowed for safety scan (milliseconds)
    max_scan_latency_ms: int = 50
    
    # Enable/disable specific scanner layers
    regex_scanner_enabled: bool = True
    bert_scanner_enabled: bool = True
    
    # Version tracking for audit trail
    pattern_version: str = "2026.01.14"


# Crisis keywords that trigger immediate bypass (regex-based safety net)
# These are hard-coded per ADR-001 - LLM never sees messages with these
CRISIS_KEYWORDS: FrozenSet[str] = frozenset({
    # Direct self-harm language
    "kill myself",
    "end my life", 
    "want to die",
    "suicide",
    "suicidal",
    
    # Methods (critical - indicates planning)
    "pills",
    "overdose",
    "bridge",
    "gun",
    "rope",
    "cut myself",
    "cutting",
    
    # Coded language (teen slang - requires regular updates)
    "unalive",
    "become a ghost",
    "final exit",
    "goodbye forever",
    "no point anymore",
    
    # Psychosis indicators
    "voices telling me",
    "they're watching me",
    "not real",
})

# Caution keywords that elevate risk score but don't trigger bypass
CAUTION_KEYWORDS: FrozenSet[str] = frozenset({
    "hopeless",
    "worthless", 
    "burden",
    "nobody cares",
    "alone",
    "can't go on",
    "give up",
    "tired of everything",
    "nothing matters",
    "don't care anymore",
    "hate myself",
    "failure",
    "trapped",
    "no way out",
    "exhausted",
    "empty inside",
})
