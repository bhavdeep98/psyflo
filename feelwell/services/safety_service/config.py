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
# Updated: 2026-01-15 - Phase 1 safety fixes: expanded patterns for adversarial evasion
CRISIS_KEYWORDS: FrozenSet[str] = frozenset({
    # ==========================================================================
    # DIRECT SELF-HARM LANGUAGE
    # ==========================================================================
    "kill myself",
    "end my life",
    "ending it all",
    "want to die",
    "suicide",
    "suicidal",
    "hurt myself",
    "harm myself",
    
    # ==========================================================================
    # METHODS (critical - indicates planning)
    # ==========================================================================
    "pills",
    "overdose",
    "took too many pills",
    "bridge",
    "gun",
    "rope",
    "noose",
    "cut myself",
    "cutting myself",
    "cutting",
    "burned myself",
    "jump off",
    "hang myself",
    
    # ==========================================================================
    # PASSIVE SUICIDAL IDEATION (coded language)
    # ==========================================================================
    "never wake up",
    "sleep forever",
    "forever nap",
    "go to sleep forever",
    "disappear forever",
    "stop existing",
    "fade away",
    "permanent solution",
    "final solution",
    "no way out",
    "can't take it anymore",
    "can't do this anymore",
    "better off without me",
    "world without me",
    "nobody would miss me",
    "nobody would care",
    "wouldn't care if i died",
    
    # ==========================================================================
    # TEEN/YOUTH CODED LANGUAGE (requires regular updates)
    # Social media slang evolves rapidly - review quarterly
    # ==========================================================================
    "unalive",
    "sewerslide",           # TikTok euphemism for suicide
    "kms",                  # kill myself
    "ctb",                  # catch the bus (suicide forum term)
    "catch the bus",        # Full phrase version
    "become a ghost",
    "final exit",
    "goodbye forever",
    "no point anymore",
    "yeet myself",
    "final yeet",           # Slang combination
    "game end",             # Gaming terminology for suicide
    "game end myself",
    "delete my save file",  # Gaming metaphor for ending life
    "respawn irl",          # Gaming metaphor implying death
    
    # ==========================================================================
    # IMMINENT PLAN INDICATORS
    # ==========================================================================
    "do it tonight",
    "going to do it",
    "written letters",      # Suicide note preparation
    "gave away",            # Giving away possessions - warning sign
    
    # ==========================================================================
    # VIOLENCE/HARM TO OTHERS
    # ==========================================================================
    "hurt other people",
    "hurt people at school",
    
    # ==========================================================================
    # ABUSE DISCLOSURE (mandatory reporting)
    # ==========================================================================
    "touches me",
    
    # ==========================================================================
    # SEVERE EATING DISORDER
    # ==========================================================================
    "haven't eaten",
    
    # ==========================================================================
    # PSYCHOSIS INDICATORS
    # ==========================================================================
    "voices telling me",
    "voices tell me",
    "they're watching me",
    "not real",
    "voices in my head",
    "voices",               # Broader catch for command hallucinations
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
