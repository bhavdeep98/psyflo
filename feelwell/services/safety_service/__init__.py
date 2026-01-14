"""Safety Service: Deterministic guardrails and crisis detection.

ADR-001: Hard-coded regex/NLP filter layer bypasses LLM for high-risk inputs.
This service is the first line of defense - every message passes through here
BEFORE reaching the LLM.

Components:
- scanner.py: SafetyScanner class with two-layer keyword detection
- config.py: Clinical thresholds and keyword sets
- handler.py: Flask HTTP endpoints (/health, /scan)
- crisis_publisher.py: Kinesis event publishing (ADR-004)

Usage:
    # As HTTP service
    POST /scan {"message": "...", "student_id": "...", "session_id": "..."}
    
    # Direct import
    from feelwell.services.safety_service.scanner import SafetyScanner
    scanner = SafetyScanner()
    result = scanner.scan(message_id, text, student_id)
"""

from .scanner import SafetyScanner, ScanResult
from .config import SafetyConfig, ClinicalThresholds, CRISIS_KEYWORDS, CAUTION_KEYWORDS
from .crisis_publisher import CrisisEventPublisher, SafetyCrisisEvent

__all__ = [
    "SafetyScanner",
    "ScanResult",
    "SafetyConfig",
    "ClinicalThresholds",
    "CRISIS_KEYWORDS",
    "CAUTION_KEYWORDS",
    "CrisisEventPublisher",
    "SafetyCrisisEvent",
]
