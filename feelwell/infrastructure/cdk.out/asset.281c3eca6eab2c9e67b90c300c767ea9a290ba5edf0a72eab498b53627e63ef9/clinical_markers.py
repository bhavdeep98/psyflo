"""Clinical marker detection for PHQ-9 and GAD-7 frameworks.

Maps conversational language to DSM-5 criteria without exposing
clinical scoring to the student.
"""
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, FrozenSet, List, Optional, Tuple

from feelwell.shared.models import ClinicalFramework, ClinicalMarker, PHQ9Item
from feelwell.shared.utils import hash_text_for_audit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarkerPattern:
    """Pattern definition for clinical marker detection."""
    framework: ClinicalFramework
    item_id: int
    patterns: FrozenSet[str]
    base_confidence: float


# PHQ-9 marker patterns mapped to conversational language
PHQ9_PATTERNS: Dict[PHQ9Item, MarkerPattern] = {
    PHQ9Item.ANHEDONIA: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=1,
        patterns=frozenset({
            "nothing is fun",
            "don't enjoy",
            "lost interest",
            "don't care about",
            "nothing feels good",
            "can't enjoy",
            "stopped doing",
            "gave up on",
            "what's the point",
            "doesn't matter anymore",
        }),
        base_confidence=0.7,
    ),
    PHQ9Item.DEPRESSED_MOOD: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=2,
        patterns=frozenset({
            "feeling down",
            "so sad",
            "depressed",
            "hopeless",
            "empty inside",
            "can't be happy",
            "nothing to look forward to",
            "life is pointless",
        }),
        base_confidence=0.75,
    ),
    PHQ9Item.SLEEP: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=3,
        patterns=frozenset({
            "can't sleep",
            "insomnia",
            "sleep all day",
            "sleeping too much",
            "wake up at night",
            "tired but can't sleep",
            "nightmares",
            "exhausted",
        }),
        base_confidence=0.65,
    ),
    PHQ9Item.FATIGUE: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=4,
        patterns=frozenset({
            "no energy",
            "so tired",
            "exhausted",
            "can't get out of bed",
            "drained",
            "worn out",
            "fatigued",
            "no motivation",
        }),
        base_confidence=0.65,
    ),
    PHQ9Item.APPETITE: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=5,
        patterns=frozenset({
            "not hungry",
            "can't eat",
            "eating too much",
            "lost appetite",
            "stress eating",
            "forgot to eat",
            "food doesn't taste good",
        }),
        base_confidence=0.6,
    ),
    PHQ9Item.GUILT: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=6,
        patterns=frozenset({
            "hate myself",
            "i'm a failure",
            "worthless",
            "burden to everyone",
            "let everyone down",
            "my fault",
            "i'm the problem",
            "don't deserve",
        }),
        base_confidence=0.8,
    ),
    PHQ9Item.CONCENTRATION: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=7,
        patterns=frozenset({
            "can't focus",
            "can't concentrate",
            "mind is blank",
            "zoning out",
            "distracted",
            "can't think straight",
            "brain fog",
        }),
        base_confidence=0.6,
    ),
    PHQ9Item.PSYCHOMOTOR: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=8,
        patterns=frozenset({
            "moving slow",
            "can't sit still",
            "restless",
            "fidgety",
            "agitated",
            "everything takes forever",
        }),
        base_confidence=0.55,
    ),
    PHQ9Item.SELF_HARM: MarkerPattern(
        framework=ClinicalFramework.PHQ9,
        item_id=9,
        patterns=frozenset({
            "hurt myself",
            "better off dead",
            "don't want to be here",
            "wish i wasn't alive",
            "end it all",
            # Note: Explicit crisis terms handled by Safety Service
        }),
        base_confidence=0.95,  # High confidence - critical marker
    ),
}

# GAD-7 marker patterns for anxiety detection
GAD7_PATTERNS: Dict[int, MarkerPattern] = {
    1: MarkerPattern(  # Feeling nervous, anxious, or on edge
        framework=ClinicalFramework.GAD7,
        item_id=1,
        patterns=frozenset({
            "so anxious",
            "nervous",
            "on edge",
            "can't relax",
            "tense",
            "wound up",
            "stressed out",
        }),
        base_confidence=0.7,
    ),
    2: MarkerPattern(  # Not being able to stop worrying
        framework=ClinicalFramework.GAD7,
        item_id=2,
        patterns=frozenset({
            "can't stop worrying",
            "overthinking",
            "mind won't stop",
            "racing thoughts",
            "worried about everything",
            "catastrophizing",
        }),
        base_confidence=0.75,
    ),
    3: MarkerPattern(  # Worrying too much about different things
        framework=ClinicalFramework.GAD7,
        item_id=3,
        patterns=frozenset({
            "worried about",
            "anxious about",
            "scared about",
            "freaking out about",
            "panicking about",
        }),
        base_confidence=0.65,
    ),
    4: MarkerPattern(  # Trouble relaxing
        framework=ClinicalFramework.GAD7,
        item_id=4,
        patterns=frozenset({
            "can't relax",
            "always tense",
            "never calm",
            "can't unwind",
            "always stressed",
        }),
        base_confidence=0.6,
    ),
    5: MarkerPattern(  # Being so restless it's hard to sit still
        framework=ClinicalFramework.GAD7,
        item_id=5,
        patterns=frozenset({
            "restless",
            "can't sit still",
            "pacing",
            "fidgeting",
            "jittery",
        }),
        base_confidence=0.6,
    ),
    6: MarkerPattern(  # Becoming easily annoyed or irritable
        framework=ClinicalFramework.GAD7,
        item_id=6,
        patterns=frozenset({
            "irritable",
            "snapping at",
            "easily annoyed",
            "angry all the time",
            "short temper",
        }),
        base_confidence=0.55,
    ),
    7: MarkerPattern(  # Feeling afraid something awful might happen
        framework=ClinicalFramework.GAD7,
        item_id=7,
        patterns=frozenset({
            "something bad will happen",
            "afraid",
            "dread",
            "sense of doom",
            "panic",
            "terrified",
        }),
        base_confidence=0.7,
    ),
}


class ClinicalMarkerDetector:
    """Detects clinical markers in conversational text.
    
    Maps student language to PHQ-9 and GAD-7 framework items
    without exposing clinical terminology to the student.
    """
    
    def __init__(self):
        """Initialize detector with compiled patterns."""
        self._phq9_compiled = self._compile_patterns(PHQ9_PATTERNS)
        self._gad7_compiled = self._compile_patterns(GAD7_PATTERNS)
        
        logger.info(
            "CLINICAL_MARKER_DETECTOR_INITIALIZED",
            extra={
                "phq9_pattern_count": len(PHQ9_PATTERNS),
                "gad7_pattern_count": len(GAD7_PATTERNS),
            }
        )
    
    def _compile_patterns(
        self, 
        patterns: Dict
    ) -> List[Tuple[re.Pattern, MarkerPattern]]:
        """Compile pattern strings into regex for efficient matching.
        
        Args:
            patterns: Dictionary of marker patterns
            
        Returns:
            List of (compiled_regex, MarkerPattern) tuples
        """
        compiled = []
        for marker_pattern in patterns.values():
            for pattern_str in marker_pattern.patterns:
                regex = re.compile(
                    rf"\b{re.escape(pattern_str)}\b",
                    re.IGNORECASE
                )
                compiled.append((regex, marker_pattern))
        return compiled
    
    def detect(self, text: str) -> List[ClinicalMarker]:
        """Detect clinical markers in text.
        
        Args:
            text: Raw message text from student
            
        Returns:
            List of detected ClinicalMarker objects
            
        Logs:
            - CLINICAL_MARKERS_DETECTED: When markers found
        """
        normalized = text.lower().strip()
        text_hash = hash_text_for_audit(text)
        markers: List[ClinicalMarker] = []
        seen_items: set = set()  # Prevent duplicate markers
        
        # Scan PHQ-9 patterns
        for regex, marker_pattern in self._phq9_compiled:
            if regex.search(normalized):
                item_key = (marker_pattern.framework, marker_pattern.item_id)
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    markers.append(ClinicalMarker(
                        framework=marker_pattern.framework,
                        item_id=marker_pattern.item_id,
                        confidence=marker_pattern.base_confidence,
                        source_text_hash=text_hash,
                    ))
        
        # Scan GAD-7 patterns
        for regex, marker_pattern in self._gad7_compiled:
            if regex.search(normalized):
                item_key = (marker_pattern.framework, marker_pattern.item_id)
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    markers.append(ClinicalMarker(
                        framework=marker_pattern.framework,
                        item_id=marker_pattern.item_id,
                        confidence=marker_pattern.base_confidence,
                        source_text_hash=text_hash,
                    ))
        
        if markers:
            logger.info(
                "CLINICAL_MARKERS_DETECTED",
                extra={
                    "text_hash": text_hash,
                    "marker_count": len(markers),
                    "frameworks": list(set(m.framework.value for m in markers)),
                    "item_ids": [m.item_id for m in markers],
                }
            )
        
        return markers
    
    def calculate_phq9_score(self, markers: List[ClinicalMarker]) -> Optional[int]:
        """Calculate approximate PHQ-9 score from detected markers.
        
        This is an ESTIMATE based on conversational markers, not a
        clinical assessment. Used for triage purposes only.
        
        Args:
            markers: List of detected clinical markers
            
        Returns:
            Estimated PHQ-9 score (0-27) or None if insufficient data
        """
        phq9_markers = [
            m for m in markers 
            if m.framework == ClinicalFramework.PHQ9
        ]
        
        if not phq9_markers:
            return None
        
        # Each detected item contributes 2-3 points based on confidence
        # PHQ-9 items are scored 0-3, we estimate based on detection
        score = 0
        for marker in phq9_markers:
            if marker.confidence >= 0.8:
                score += 3  # High confidence = severe
            elif marker.confidence >= 0.6:
                score += 2  # Medium confidence = moderate
            else:
                score += 1  # Low confidence = mild
        
        return min(score, 27)  # Cap at max PHQ-9 score
    
    def calculate_gad7_score(self, markers: List[ClinicalMarker]) -> Optional[int]:
        """Calculate approximate GAD-7 score from detected markers.
        
        Args:
            markers: List of detected clinical markers
            
        Returns:
            Estimated GAD-7 score (0-21) or None if insufficient data
        """
        gad7_markers = [
            m for m in markers 
            if m.framework == ClinicalFramework.GAD7
        ]
        
        if not gad7_markers:
            return None
        
        score = 0
        for marker in gad7_markers:
            if marker.confidence >= 0.8:
                score += 3
            elif marker.confidence >= 0.6:
                score += 2
            else:
                score += 1
        
        return min(score, 21)  # Cap at max GAD-7 score
