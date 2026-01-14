"""Risk level and clinical marker domain models.

This file defines the core enums and data structures for risk assessment.
Following ADR-001: Deterministic guardrails with explicit risk levels.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class RiskLevel(Enum):
    """Risk classification levels for student messages.
    
    Based on clinical severity thresholds from PHQ-9 guidelines.
    Source: https://www.apa.org/depression-guideline/patient-health-questionnaire.pdf
    """
    SAFE = "safe"           # Score 0-4: Self-help resources appropriate
    CAUTION = "caution"     # Score 5-9: Counselor referral suggested
    CRISIS = "crisis"       # Score 10+ or red flags: Immediate intervention


class ClinicalFramework(Enum):
    """Validated clinical assessment frameworks for adolescent mental health."""
    PHQ9 = "phq9"           # Patient Health Questionnaire (Depression)
    GAD7 = "gad7"           # Generalized Anxiety Disorder scale
    CSSRS = "cssrs"         # Columbia Suicide Severity Rating Scale
    SCARED = "scared"       # Screen for Child Anxiety Related Disorders


class PHQ9Item(Enum):
    """PHQ-9 questionnaire items mapped to conversational markers.
    
    Each item represents a DSM-5 criterion for Major Depressive Disorder.
    """
    ANHEDONIA = 1           # Little interest or pleasure in doing things
    DEPRESSED_MOOD = 2      # Feeling down, depressed, or hopeless
    SLEEP = 3               # Trouble falling/staying asleep, or sleeping too much
    FATIGUE = 4             # Feeling tired or having little energy
    APPETITE = 5            # Poor appetite or overeating
    GUILT = 6               # Feeling bad about yourself
    CONCENTRATION = 7       # Trouble concentrating
    PSYCHOMOTOR = 8         # Moving/speaking slowly or being fidgety
    SELF_HARM = 9           # Thoughts of self-harm (CRITICAL - triggers crisis path)


@dataclass(frozen=True)
class ClinicalMarker:
    """An identified clinical indicator from user text.
    
    Immutable by design - markers cannot be modified after detection.
    """
    framework: ClinicalFramework
    item_id: int
    confidence: float       # 0.0 to 1.0 confidence score
    source_text_hash: str   # Hash of triggering text (no raw PII per ADR-003)
    detected_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")


@dataclass(frozen=True)
class CurrentSnapshot:
    """Layer 1: Real-time risk assessment for a single message.
    
    Represents the immediate reading of a student's message.
    Stored in MongoDB as part of conversation transcript.
    """
    message_id: str
    session_id: str
    student_id_hash: str    # Hashed per ADR-003
    risk_score: float       # 0.0 to 1.0
    risk_level: RiskLevel
    markers: List[ClinicalMarker] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        if not 0.0 <= self.risk_score <= 1.0:
            raise ValueError(f"Risk score must be 0.0-1.0, got {self.risk_score}")


@dataclass(frozen=True)
class SessionSummary:
    """Layer 2: Aggregated analysis of a complete conversation session.
    
    Generated after session ends. Stored in PostgreSQL session_summaries table.
    """
    session_id: str
    student_id_hash: str
    duration_minutes: int
    message_count: int
    start_risk_score: float
    end_risk_score: float
    phq9_score: Optional[int] = None    # 0-27 scale
    gad7_score: Optional[int] = None    # 0-21 scale
    risk_trajectory: str = "stable"      # "stable", "improving", "escalating"
    counselor_flag: bool = False
    markers_detected: List[ClinicalMarker] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_escalating(self) -> bool:
        """Check if risk increased during session."""
        return self.end_risk_score > self.start_risk_score + 0.2
