"""Category mapping for clinical datasets.

Maps various clinical categories and severity scores to
Feelwell's triage levels (safe, caution, crisis).

Based on clinical guidelines:
- PHQ-9: 0-4 minimal, 5-9 mild, 10-14 moderate, 15-19 moderately severe, 20-27 severe
- GAD-7: 0-4 minimal, 5-9 mild, 10-14 moderate, 15-21 severe
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TriageCategory(Enum):
    """Feelwell triage categories."""
    SAFE = "safe"
    CAUTION = "caution"
    CRISIS = "crisis"


class ClinicalCategory(Enum):
    """Clinical condition categories."""
    DEPRESSION = "depression"
    ANXIETY = "anxiety"
    SUICIDAL_IDEATION = "suicidal_ideation"
    SELF_HARM = "self_harm"
    TRAUMA = "trauma"
    GRIEF = "grief"
    STRESS = "stress"
    RELATIONSHIP = "relationship"
    ACADEMIC = "academic"
    GENERAL_SUPPORT = "general_support"
    CRISIS = "crisis"
    ABUSE = "abuse"


@dataclass
class PHQ9Thresholds:
    """PHQ-9 severity thresholds per clinical guidelines.
    
    Source: Kroenke et al., 2001
    https://www.apa.org/depression-guideline/patient-health-questionnaire.pdf
    """
    MINIMAL_MAX: int = 4
    MILD_MAX: int = 9
    MODERATE_MAX: int = 14
    MODERATELY_SEVERE_MAX: int = 19
    SEVERE_MAX: int = 27
    
    # Item 9 (suicidal ideation) thresholds
    ITEM9_CRISIS_THRESHOLD: int = 1  # Any positive response = crisis


@dataclass
class GAD7Thresholds:
    """GAD-7 severity thresholds per clinical guidelines.
    
    Source: Spitzer et al., 2006
    """
    MINIMAL_MAX: int = 4
    MILD_MAX: int = 9
    MODERATE_MAX: int = 14
    SEVERE_MAX: int = 21


class CategoryMapper:
    """Maps clinical categories and scores to triage levels.
    
    Implements evidence-based mapping from clinical assessments
    to Feelwell's three-tier triage system.
    """
    
    # Keywords that indicate crisis regardless of score
    CRISIS_KEYWORDS = {
        "suicide", "suicidal", "kill myself", "end my life",
        "self-harm", "cutting", "hurt myself", "overdose",
        "abuse", "assault", "violence", "homicidal",
        "psychosis", "hallucination", "voices telling me",
    }
    
    # Category to default triage mapping
    CATEGORY_DEFAULTS = {
        ClinicalCategory.SUICIDAL_IDEATION: TriageCategory.CRISIS,
        ClinicalCategory.SELF_HARM: TriageCategory.CRISIS,
        ClinicalCategory.ABUSE: TriageCategory.CRISIS,
        ClinicalCategory.CRISIS: TriageCategory.CRISIS,
        ClinicalCategory.TRAUMA: TriageCategory.CAUTION,
        ClinicalCategory.DEPRESSION: TriageCategory.CAUTION,
        ClinicalCategory.ANXIETY: TriageCategory.CAUTION,
        ClinicalCategory.GRIEF: TriageCategory.CAUTION,
        ClinicalCategory.STRESS: TriageCategory.SAFE,
        ClinicalCategory.RELATIONSHIP: TriageCategory.SAFE,
        ClinicalCategory.ACADEMIC: TriageCategory.SAFE,
        ClinicalCategory.GENERAL_SUPPORT: TriageCategory.SAFE,
    }
    
    # MentalChat16K topic mappings
    MENTALCHAT_TOPIC_MAP = {
        "depression": ClinicalCategory.DEPRESSION,
        "anxiety": ClinicalCategory.ANXIETY,
        "stress": ClinicalCategory.STRESS,
        "trauma": ClinicalCategory.TRAUMA,
        "grief": ClinicalCategory.GRIEF,
        "relationship": ClinicalCategory.RELATIONSHIP,
        "self-harm": ClinicalCategory.SELF_HARM,
        "suicidal": ClinicalCategory.SUICIDAL_IDEATION,
        "abuse": ClinicalCategory.ABUSE,
        "general": ClinicalCategory.GENERAL_SUPPORT,
    }
    
    def __init__(
        self,
        phq9_thresholds: Optional[PHQ9Thresholds] = None,
        gad7_thresholds: Optional[GAD7Thresholds] = None,
    ):
        """Initialize mapper with thresholds.
        
        Args:
            phq9_thresholds: PHQ-9 severity thresholds
            gad7_thresholds: GAD-7 severity thresholds
        """
        self.phq9 = phq9_thresholds or PHQ9Thresholds()
        self.gad7 = gad7_thresholds or GAD7Thresholds()
        
        logger.info("CATEGORY_MAPPER_INITIALIZED")
    
    def map_phq9_to_triage(
        self,
        total_score: int,
        item9_score: Optional[int] = None,
    ) -> TriageCategory:
        """Map PHQ-9 score to triage level.
        
        Args:
            total_score: PHQ-9 total score (0-27)
            item9_score: Item 9 (suicidal ideation) score (0-3)
            
        Returns:
            TriageCategory
        """
        # Item 9 (suicidal ideation) takes precedence
        if item9_score is not None and item9_score >= self.phq9.ITEM9_CRISIS_THRESHOLD:
            logger.info(
                "PHQ9_CRISIS_ITEM9",
                extra={"item9_score": item9_score, "total_score": total_score}
            )
            return TriageCategory.CRISIS
        
        # Map by total score
        if total_score >= 20:  # Severe
            return TriageCategory.CRISIS
        elif total_score >= 15:  # Moderately severe
            return TriageCategory.CAUTION
        elif total_score >= 10:  # Moderate
            return TriageCategory.CAUTION
        elif total_score >= 5:  # Mild
            return TriageCategory.SAFE
        else:  # Minimal
            return TriageCategory.SAFE
    
    def map_gad7_to_triage(self, total_score: int) -> TriageCategory:
        """Map GAD-7 score to triage level.
        
        Args:
            total_score: GAD-7 total score (0-21)
            
        Returns:
            TriageCategory
        """
        if total_score >= 15:  # Severe
            return TriageCategory.CAUTION  # Anxiety alone rarely crisis
        elif total_score >= 10:  # Moderate
            return TriageCategory.CAUTION
        elif total_score >= 5:  # Mild
            return TriageCategory.SAFE
        else:  # Minimal
            return TriageCategory.SAFE
    
    def map_category_to_triage(
        self,
        category: str,
        text: Optional[str] = None,
        severity_score: Optional[float] = None,
    ) -> TriageCategory:
        """Map clinical category to triage level.
        
        Args:
            category: Clinical category string
            text: Optional text to check for crisis keywords
            severity_score: Optional severity score (0-1)
            
        Returns:
            TriageCategory
        """
        # Check text for crisis keywords first
        if text:
            text_lower = text.lower()
            for keyword in self.CRISIS_KEYWORDS:
                if keyword in text_lower:
                    return TriageCategory.CRISIS
        
        # Map category string to enum
        category_lower = category.lower()
        clinical_cat = None
        
        for key, cat in self.MENTALCHAT_TOPIC_MAP.items():
            if key in category_lower:
                clinical_cat = cat
                break
        
        if clinical_cat is None:
            clinical_cat = ClinicalCategory.GENERAL_SUPPORT
        
        # Get default triage for category
        default_triage = self.CATEGORY_DEFAULTS.get(
            clinical_cat, 
            TriageCategory.SAFE
        )
        
        # Adjust by severity score if provided
        if severity_score is not None:
            if severity_score >= 0.8:
                # High severity can escalate to crisis
                if default_triage == TriageCategory.CAUTION:
                    return TriageCategory.CRISIS
                return TriageCategory.CAUTION
            elif severity_score >= 0.5:
                # Medium severity at least caution
                if default_triage == TriageCategory.SAFE:
                    return TriageCategory.CAUTION
        
        return default_triage
    
    def map_mentalchat_topic(self, topic: str) -> tuple:
        """Map MentalChat16K topic to category and triage.
        
        Args:
            topic: Topic string from MentalChat16K
            
        Returns:
            Tuple of (category_string, triage_level)
        """
        topic_lower = topic.lower()
        
        for key, cat in self.MENTALCHAT_TOPIC_MAP.items():
            if key in topic_lower:
                triage = self.CATEGORY_DEFAULTS.get(cat, TriageCategory.SAFE)
                return cat.value, triage.value
        
        return "general_support", TriageCategory.SAFE.value
    
    def map_clinical_decision(
        self,
        decision_type: str,
        urgency: Optional[str] = None,
    ) -> TriageCategory:
        """Map clinical decision task to triage level.
        
        Args:
            decision_type: Type of clinical decision
            urgency: Urgency level if provided
            
        Returns:
            TriageCategory
        """
        decision_lower = decision_type.lower()
        
        # Immediate intervention decisions
        if any(kw in decision_lower for kw in ["emergency", "crisis", "immediate", "urgent"]):
            return TriageCategory.CRISIS
        
        # Monitoring/follow-up decisions
        if any(kw in decision_lower for kw in ["monitor", "follow-up", "refer", "treatment"]):
            return TriageCategory.CAUTION
        
        # Routine decisions
        if any(kw in decision_lower for kw in ["routine", "maintenance", "stable"]):
            return TriageCategory.SAFE
        
        # Check urgency if provided
        if urgency:
            urgency_lower = urgency.lower()
            if "high" in urgency_lower or "immediate" in urgency_lower:
                return TriageCategory.CRISIS
            elif "medium" in urgency_lower or "moderate" in urgency_lower:
                return TriageCategory.CAUTION
        
        return TriageCategory.SAFE
    
    def get_severity_from_phq9(self, score: int) -> float:
        """Convert PHQ-9 score to 0-1 severity.
        
        Args:
            score: PHQ-9 total score
            
        Returns:
            Severity score 0-1
        """
        return min(1.0, score / 27.0)
    
    def get_severity_from_gad7(self, score: int) -> float:
        """Convert GAD-7 score to 0-1 severity.
        
        Args:
            score: GAD-7 total score
            
        Returns:
            Severity score 0-1
        """
        return min(1.0, score / 21.0)
