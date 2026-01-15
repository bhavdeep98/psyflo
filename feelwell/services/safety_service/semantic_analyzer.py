"""Semantic analyzer for clinical language understanding.

Adds deterministic semantic understanding to the safety pipeline.
Each layer produces explainable scores based on clinical frameworks.

Architecture:
- Layer 1: Keyword matching (existing SafetyScanner)
- Layer 2: Clinical marker detection (PHQ-9, GAD-7 patterns)
- Layer 3: Semantic similarity to clinical phrases
- Layer 4: Sentiment polarity analysis

All layers are deterministic and produce traceable explanations.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ClinicalFramework(Enum):
    """Supported clinical assessment frameworks."""
    PHQ9 = "phq9"  # Depression
    GAD7 = "gad7"  # Anxiety
    CSSRS = "cssrs"  # Suicide risk (Columbia Protocol)
    PCL5 = "pcl5"  # PTSD


@dataclass(frozen=True)
class ClinicalMarker:
    """A detected clinical marker with explanation."""
    framework: ClinicalFramework
    item_number: int
    item_name: str
    severity: int  # 0-3 scale matching PHQ-9/GAD-7
    matched_phrase: str
    explanation: str
    
    @property
    def is_critical(self) -> bool:
        """Check if this is a critical marker (e.g., PHQ-9 item 9)."""
        return (
            (self.framework == ClinicalFramework.PHQ9 and self.item_number == 9) or
            (self.framework == ClinicalFramework.CSSRS and self.item_number >= 4)
        )


@dataclass
class SemanticAnalysisResult:
    """Result of semantic analysis with full explainability."""
    # Clinical markers detected
    markers: List[ClinicalMarker] = field(default_factory=list)
    
    # Framework scores
    phq9_estimated_score: int = 0
    gad7_estimated_score: int = 0
    
    # Semantic similarity scores
    crisis_similarity: float = 0.0
    hopelessness_similarity: float = 0.0
    self_harm_similarity: float = 0.0
    
    # Sentiment
    sentiment_polarity: float = 0.0  # -1 to 1
    sentiment_intensity: float = 0.0  # 0 to 1
    
    # Combined risk assessment
    semantic_risk_score: float = 0.0
    risk_factors: List[str] = field(default_factory=list)
    protective_factors: List[str] = field(default_factory=list)
    
    # Explainability
    explanation: str = ""
    confidence: float = 0.0
    
    def has_critical_markers(self) -> bool:
        """Check if any critical markers were detected."""
        return any(m.is_critical for m in self.markers)
    
    def to_dict(self) -> Dict:
        return {
            "markers": [
                {
                    "framework": m.framework.value,
                    "item": m.item_number,
                    "name": m.item_name,
                    "severity": m.severity,
                    "matched": m.matched_phrase,
                    "critical": m.is_critical,
                }
                for m in self.markers
            ],
            "phq9_score": self.phq9_estimated_score,
            "gad7_score": self.gad7_estimated_score,
            "semantic_risk_score": round(self.semantic_risk_score, 3),
            "risk_factors": self.risk_factors,
            "protective_factors": self.protective_factors,
            "explanation": self.explanation,
            "confidence": round(self.confidence, 3),
        }


# PHQ-9 Clinical Patterns - each item maps to specific language patterns
PHQ9_PATTERNS: Dict[int, Dict] = {
    1: {
        "name": "anhedonia",
        "description": "Little interest or pleasure in doing things",
        "patterns": [
            (r"\b(don'?t|no longer|lost|losing)\s+(care|interest|enjoy|like)\b", 2),
            (r"\b(nothing|anything)\s+(is\s+)?fun\b", 2),
            (r"\bwhat'?s\s+the\s+point\b", 2),
            (r"\bdon'?t\s+want\s+to\s+do\s+anything\b", 3),
            (r"\bcan'?t\s+(enjoy|find\s+pleasure)\b", 2),
            (r"\bused\s+to\s+(love|enjoy).+but\s+(now|anymore)\b", 2),
            (r"\bnothing\s+makes\s+me\s+happy\b", 3),
        ],
    },
    2: {
        "name": "depressed_mood",
        "description": "Feeling down, depressed, or hopeless",
        "patterns": [
            (r"\b(feel(ing)?|been)\s+(down|depressed|sad|low|blue)\b", 2),
            (r"\bhopeless(ness)?\b", 3),
            (r"\bno\s+hope\b", 3),
            (r"\bwhat'?s\s+the\s+point\b", 2),
            (r"\blife\s+(is|feels)\s+(meaningless|empty|pointless)\b", 3),
            (r"\bcan'?t\s+see\s+(a\s+)?future\b", 3),
            (r"\bthings\s+will\s+never\s+get\s+better\b", 3),
        ],
    },
    3: {
        "name": "sleep_disturbance",
        "description": "Trouble falling or staying asleep, or sleeping too much",
        "patterns": [
            (r"\bcan'?t\s+sleep\b", 2),
            (r"\b(trouble|difficulty|hard\s+time)\s+(falling|staying)\s+asleep\b", 2),
            (r"\binsomnia\b", 2),
            (r"\bsleep(ing)?\s+(all\s+day|too\s+much|\d+\s+hours)\b", 2),
            (r"\bwake\s+up\s+(at\s+night|early|multiple\s+times)\b", 2),
            (r"\bexhausted\s+but\s+can'?t\s+sleep\b", 3),
        ],
    },
    4: {
        "name": "fatigue",
        "description": "Feeling tired or having little energy",
        "patterns": [
            (r"\b(so\s+)?(tired|exhausted|drained|fatigued)\b", 2),
            (r"\bno\s+energy\b", 2),
            (r"\bcan'?t\s+get\s+out\s+of\s+bed\b", 3),
            (r"\beverything\s+(takes|requires)\s+(so\s+much\s+)?effort\b", 2),
            (r"\bfeels?\s+like\s+i'?m\s+(dragging|underwater)\b", 2),
        ],
    },
    5: {
        "name": "appetite_change",
        "description": "Poor appetite or overeating",
        "patterns": [
            (r"\b(not|no|lost)\s+(hungry|appetite)\b", 2),
            (r"\bcan'?t\s+(eat|stop\s+eating)\b", 2),
            (r"\b(barely|haven'?t)\s+eaten\b", 2),
            (r"\beating\s+(too\s+much|all\s+the\s+time|constantly)\b", 2),
            (r"\bfood\s+(doesn'?t|don'?t)\s+(taste|appeal)\b", 2),
        ],
    },
    6: {
        "name": "worthlessness",
        "description": "Feeling bad about yourself or that you are a failure",
        "patterns": [
            (r"\b(i'?m|feel(ing)?)\s+(a\s+)?(failure|worthless|useless)\b", 3),
            (r"\bhate\s+myself\b", 3),
            (r"\bi'?m\s+(no\s+good|not\s+good\s+enough)\b", 2),
            (r"\beveryone\s+would\s+be\s+better\s+off\s+without\s+me\b", 3),
            (r"\bi\s+(let|disappoint)\s+everyone\s+down\b", 2),
            (r"\bi'?m\s+a\s+burden\b", 3),
            (r"\bcan'?t\s+do\s+anything\s+right\b", 2),
        ],
    },
    7: {
        "name": "concentration",
        "description": "Trouble concentrating on things",
        "patterns": [
            (r"\bcan'?t\s+(focus|concentrate|think)\b", 2),
            (r"\bmind\s+(goes\s+blank|wanders|racing)\b", 2),
            (r"\b(trouble|difficulty)\s+(concentrating|focusing)\b", 2),
            (r"\bcan'?t\s+(read|follow|remember)\b", 1),
        ],
    },
    8: {
        "name": "psychomotor",
        "description": "Moving or speaking slowly, or being fidgety/restless",
        "patterns": [
            (r"\b(moving|speaking)\s+(slowly|slow)\b", 2),
            (r"\bcan'?t\s+sit\s+still\b", 2),
            (r"\b(restless|fidgety|agitated)\b", 2),
            (r"\bfeels?\s+like\s+(i'?m\s+)?(underwater|in\s+slow\s+motion)\b", 2),
            (r"\bpacing\b", 1),
        ],
    },
    9: {
        "name": "suicidal_ideation",
        "description": "Thoughts of being better off dead or hurting yourself",
        "patterns": [
            # Direct expressions
            (r"\bbetter\s+off\s+dead\b", 3),
            (r"\bwish\s+i\s+(was|were)\s+(dead|gone|never\s+born)\b", 3),
            (r"\bthink(ing)?\s+about\s+(death|dying|ending\s+it)\b", 3),
            (r"\bdon'?t\s+want\s+to\s+(be\s+here|exist|live|wake\s+up)\b", 3),
            (r"\bhurt(ing)?\s+myself\b", 3),
            (r"\bself[- ]?harm\b", 3),
            (r"\bcut(ting)?\s+(myself|my\s+(arm|wrist|leg))\b", 3),
            # Passive suicidal ideation / coded language
            (r"\b(go\s+to\s+)?sleep\s+(and\s+)?never\s+wake\s+up\b", 3),
            (r"\bfall\s+asleep\s+(and\s+)?(never|not)\s+(wake|get)\s+up\b", 3),
            (r"\bdisappear\s+(forever|completely)\b", 3),
            (r"\bjust\s+(want\s+to\s+)?disappear\b", 3),
            (r"\bwant\s+(it\s+)?(all\s+)?to\s+(be\s+over|end|stop)\b", 3),
            (r"\bcan'?t\s+(do|take)\s+(this|it)\s+anymore\b", 3),
            (r"\bno\s+(reason|point)\s+(to\s+)?(keep\s+)?(going|living|trying)\b", 3),
            (r"\bwhy\s+(even\s+)?(bother|try|continue)\b", 2),
            (r"\bwouldn'?t\s+(care|mind)\s+if\s+i\s+(died|wasn'?t\s+here)\b", 3),
            (r"\bnobody\s+would\s+(miss|notice|care)\s+(if\s+i)?\b", 3),
            (r"\bworld\s+would\s+be\s+better\s+without\s+me\b", 3),
            (r"\bfade\s+away\b", 2),
            (r"\bstop\s+existing\b", 3),
            (r"\bcheck\s+out\b", 2),  # euphemism
            (r"\bpeace(ful)?\s+(finally|at\s+last)\b", 2),  # context-dependent
            (r"\bfinal\s+(solution|answer|way\s+out)\b", 3),
            (r"\bpermanent\s+(solution|escape|end)\b", 3),
            (r"\bno\s+way\s+out\b", 3),
            (r"\btrapped\s+(with\s+)?no\s+(escape|exit|way)\b", 3),
            # Teen/youth coded language
            (r"\bunalive\b", 3),  # TikTok euphemism
            (r"\bkms\b", 3),  # "kill myself" abbreviation
            (r"\bctb\b", 3),  # "catch the bus" - suicide forum term
            (r"\bsw\b", 3),  # "self-wounding" abbreviation
            (r"\byeet\s+(myself|me)\s+(off|out)\b", 3),  # youth slang
            # Note: Explicit crisis keywords are handled by Layer 1
        ],
    },
}


# GAD-7 Clinical Patterns
GAD7_PATTERNS: Dict[int, Dict] = {
    1: {
        "name": "nervousness",
        "description": "Feeling nervous, anxious, or on edge",
        "patterns": [
            (r"\b(nervous|anxious|on\s+edge|tense)\b", 2),
            (r"\bcan'?t\s+(relax|calm\s+down)\b", 2),
            (r"\balways\s+worried\b", 2),
        ],
    },
    2: {
        "name": "uncontrollable_worry",
        "description": "Not being able to stop or control worrying",
        "patterns": [
            (r"\bcan'?t\s+stop\s+worrying\b", 3),
            (r"\bworry(ing)?\s+(all\s+the\s+time|constantly|about\s+everything)\b", 2),
            (r"\bthoughts\s+(won'?t|don'?t)\s+stop\b", 2),
            (r"\boverthink(ing)?\b", 1),
        ],
    },
    3: {
        "name": "excessive_worry",
        "description": "Worrying too much about different things",
        "patterns": [
            (r"\bworry\s+about\s+everything\b", 2),
            (r"\b(always|constantly)\s+thinking\s+about\s+what\s+(could|might)\b", 2),
            (r"\bwhat\s+if\b.*\bwhat\s+if\b", 2),  # Multiple "what ifs"
        ],
    },
    4: {
        "name": "difficulty_relaxing",
        "description": "Trouble relaxing",
        "patterns": [
            (r"\bcan'?t\s+relax\b", 2),
            (r"\b(hard|difficult|trouble)\s+(to\s+)?relax(ing)?\b", 2),
            (r"\balways\s+(tense|wound\s+up)\b", 2),
        ],
    },
    5: {
        "name": "restlessness",
        "description": "Being so restless that it's hard to sit still",
        "patterns": [
            (r"\b(so\s+)?restless\b", 2),
            (r"\bcan'?t\s+sit\s+still\b", 2),
            (r"\bpacing\b", 1),
            (r"\bfeel\s+like\s+i\s+(need|have)\s+to\s+(move|do\s+something)\b", 2),
        ],
    },
    6: {
        "name": "irritability",
        "description": "Becoming easily annoyed or irritable",
        "patterns": [
            (r"\b(easily\s+)?(annoyed|irritated|irritable|angry)\b", 2),
            (r"\bsnap(ping)?\s+at\s+(people|everyone)\b", 2),
            (r"\beverything\s+(annoys|bothers)\s+me\b", 2),
            (r"\bshort\s+(temper|fuse)\b", 2),
        ],
    },
    7: {
        "name": "fear_of_awful",
        "description": "Feeling afraid as if something awful might happen",
        "patterns": [
            (r"\bsomething\s+(bad|awful|terrible)\s+(is\s+going\s+to|will|might)\s+happen\b", 3),
            (r"\bimpending\s+doom\b", 3),
            (r"\bafraid\s+(all\s+the\s+time|constantly)\b", 2),
            (r"\bpanic\s+(attack|attacks)\b", 3),
            (r"\bheart\s+(racing|pounding)\b", 2),
            (r"\bcan'?t\s+breathe\b", 2),
        ],
    },
}

# Protective factor patterns
PROTECTIVE_PATTERNS: List[Tuple[str, str]] = [
    (r"\b(getting|feeling)\s+(better|help|support)\b", "seeking_help"),
    (r"\b(talk(ing|ed)?|spoke)\s+(to|with)\s+(someone|therapist|counselor|friend|family)\b", "social_support"),
    (r"\b(have|got)\s+(hope|plans|goals)\b", "future_orientation"),
    (r"\b(exercise|workout|gym|running|walking)\b", "physical_activity"),
    (r"\b(medication|meds|therapy|treatment)\s+(is\s+)?(helping|working)\b", "treatment_engagement"),
    (r"\b(grateful|thankful|appreciate)\b", "gratitude"),
    (r"\b(coping|managing|handling)\s+(it|things|okay)\b", "coping_skills"),
]


class SemanticAnalyzer:
    """Deterministic semantic analyzer for clinical language.
    
    Provides explainable risk assessment based on:
    1. Clinical marker detection (PHQ-9, GAD-7 patterns)
    2. Protective factor identification
    3. Combined risk scoring with full traceability
    
    All analysis is deterministic - same input always produces same output.
    """
    
    def __init__(self):
        """Initialize analyzer with compiled patterns."""
        # Compile PHQ-9 patterns
        self._phq9_compiled: Dict[int, List[Tuple[re.Pattern, int]]] = {}
        for item_num, item_data in PHQ9_PATTERNS.items():
            self._phq9_compiled[item_num] = [
                (re.compile(pattern, re.IGNORECASE), severity)
                for pattern, severity in item_data["patterns"]
            ]
        
        # Compile GAD-7 patterns
        self._gad7_compiled: Dict[int, List[Tuple[re.Pattern, int]]] = {}
        for item_num, item_data in GAD7_PATTERNS.items():
            self._gad7_compiled[item_num] = [
                (re.compile(pattern, re.IGNORECASE), severity)
                for pattern, severity in item_data["patterns"]
            ]
        
        # Compile protective patterns
        self._protective_compiled = [
            (re.compile(pattern, re.IGNORECASE), factor_name)
            for pattern, factor_name in PROTECTIVE_PATTERNS
        ]
        
        logger.info("SEMANTIC_ANALYZER_INITIALIZED", extra={
            "phq9_items": len(self._phq9_compiled),
            "gad7_items": len(self._gad7_compiled),
            "protective_patterns": len(self._protective_compiled),
        })
    
    def analyze(self, text: str) -> SemanticAnalysisResult:
        """Perform semantic analysis on text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            SemanticAnalysisResult with full explainability
        """
        result = SemanticAnalysisResult()
        normalized_text = text.lower().strip()
        
        # Layer 2: Clinical marker detection
        phq9_markers = self._detect_phq9_markers(normalized_text)
        gad7_markers = self._detect_gad7_markers(normalized_text)
        result.markers = phq9_markers + gad7_markers
        
        # Calculate estimated scores
        result.phq9_estimated_score = self._calculate_phq9_score(phq9_markers)
        result.gad7_estimated_score = self._calculate_gad7_score(gad7_markers)
        
        # Detect protective factors
        result.protective_factors = self._detect_protective_factors(normalized_text)
        
        # Build risk factors list
        result.risk_factors = self._build_risk_factors(result.markers)
        
        # Calculate combined semantic risk score
        result.semantic_risk_score = self._calculate_semantic_risk(result)
        
        # Generate explanation
        result.explanation = self._generate_explanation(result)
        result.confidence = self._calculate_confidence(result)
        
        logger.info("SEMANTIC_ANALYSIS_COMPLETED", extra={
            "markers_detected": len(result.markers),
            "phq9_score": result.phq9_estimated_score,
            "gad7_score": result.gad7_estimated_score,
            "risk_score": round(result.semantic_risk_score, 3),
            "has_critical": result.has_critical_markers(),
        })
        
        return result
    
    def _detect_phq9_markers(self, text: str) -> List[ClinicalMarker]:
        """Detect PHQ-9 clinical markers in text."""
        markers = []
        
        for item_num, patterns in self._phq9_compiled.items():
            item_data = PHQ9_PATTERNS[item_num]
            
            for pattern, severity in patterns:
                match = pattern.search(text)
                if match:
                    markers.append(ClinicalMarker(
                        framework=ClinicalFramework.PHQ9,
                        item_number=item_num,
                        item_name=item_data["name"],
                        severity=severity,
                        matched_phrase=match.group(),
                        explanation=f"PHQ-9 Item {item_num}: {item_data['description']}",
                    ))
                    break  # Only count each item once
        
        return markers
    
    def _detect_gad7_markers(self, text: str) -> List[ClinicalMarker]:
        """Detect GAD-7 clinical markers in text."""
        markers = []
        
        for item_num, patterns in self._gad7_compiled.items():
            item_data = GAD7_PATTERNS[item_num]
            
            for pattern, severity in patterns:
                match = pattern.search(text)
                if match:
                    markers.append(ClinicalMarker(
                        framework=ClinicalFramework.GAD7,
                        item_number=item_num,
                        item_name=item_data["name"],
                        severity=severity,
                        matched_phrase=match.group(),
                        explanation=f"GAD-7 Item {item_num}: {item_data['description']}",
                    ))
                    break
        
        return markers
    
    def _detect_protective_factors(self, text: str) -> List[str]:
        """Detect protective factors in text."""
        factors = []
        for pattern, factor_name in self._protective_compiled:
            if pattern.search(text):
                factors.append(factor_name)
        return factors
    
    def _calculate_phq9_score(self, markers: List[ClinicalMarker]) -> int:
        """Estimate PHQ-9 score from detected markers."""
        phq9_markers = [m for m in markers if m.framework == ClinicalFramework.PHQ9]
        return sum(m.severity for m in phq9_markers)
    
    def _calculate_gad7_score(self, markers: List[ClinicalMarker]) -> int:
        """Estimate GAD-7 score from detected markers."""
        gad7_markers = [m for m in markers if m.framework == ClinicalFramework.GAD7]
        return sum(m.severity for m in gad7_markers)

    def _build_risk_factors(self, markers: List[ClinicalMarker]) -> List[str]:
        """Build list of identified risk factors."""
        factors = []
        
        # Check for critical markers
        if any(m.is_critical for m in markers):
            factors.append("suicidal_ideation_detected")
        
        # Check for multiple depression symptoms
        phq9_count = len([m for m in markers if m.framework == ClinicalFramework.PHQ9])
        if phq9_count >= 5:
            factors.append("multiple_depression_symptoms")
        elif phq9_count >= 3:
            factors.append("several_depression_symptoms")
        
        # Check for anxiety symptoms
        gad7_count = len([m for m in markers if m.framework == ClinicalFramework.GAD7])
        if gad7_count >= 4:
            factors.append("significant_anxiety_symptoms")
        
        # Check for hopelessness (PHQ-9 item 2)
        if any(m.item_number == 2 and m.framework == ClinicalFramework.PHQ9 for m in markers):
            factors.append("hopelessness_present")
        
        # Check for worthlessness (PHQ-9 item 6)
        if any(m.item_number == 6 and m.framework == ClinicalFramework.PHQ9 for m in markers):
            factors.append("worthlessness_present")
        
        return factors
    
    def _calculate_semantic_risk(self, result: SemanticAnalysisResult) -> float:
        """Calculate combined semantic risk score (0.0 to 1.0).
        
        Scoring is deterministic and based on clinical thresholds:
        - PHQ-9 >= 20 (severe): 0.9+
        - PHQ-9 15-19 (moderately severe): 0.7-0.9
        - PHQ-9 10-14 (moderate): 0.5-0.7
        - PHQ-9 5-9 (mild): 0.3-0.5
        - PHQ-9 0-4 (minimal): 0.1-0.3
        
        Critical markers (suicidal ideation) override to 1.0
        Protective factors reduce score by up to 0.1
        """
        # Critical marker override
        if result.has_critical_markers():
            return 1.0
        
        # Base score from PHQ-9
        phq9 = result.phq9_estimated_score
        if phq9 >= 20:
            base_score = 0.9 + min(0.1, (phq9 - 20) * 0.01)
        elif phq9 >= 15:
            base_score = 0.7 + (phq9 - 15) * 0.04
        elif phq9 >= 10:
            base_score = 0.5 + (phq9 - 10) * 0.04
        elif phq9 >= 5:
            base_score = 0.3 + (phq9 - 5) * 0.04
        else:
            base_score = 0.1 + phq9 * 0.04
        
        # Add GAD-7 contribution (anxiety comorbidity increases risk)
        gad7 = result.gad7_estimated_score
        if gad7 >= 10:
            base_score += 0.1
        elif gad7 >= 5:
            base_score += 0.05
        
        # Protective factor reduction
        protective_reduction = len(result.protective_factors) * 0.02
        base_score = max(0.1, base_score - protective_reduction)
        
        return min(1.0, base_score)
    
    def _generate_explanation(self, result: SemanticAnalysisResult) -> str:
        """Generate human-readable explanation of analysis."""
        parts = []
        
        # Critical marker warning
        if result.has_critical_markers():
            parts.append("⚠️ CRITICAL: Suicidal ideation indicators detected.")
        
        # PHQ-9 summary
        if result.phq9_estimated_score > 0:
            severity = self._get_phq9_severity_label(result.phq9_estimated_score)
            parts.append(f"Depression indicators: {severity} (estimated PHQ-9: {result.phq9_estimated_score})")
        
        # GAD-7 summary
        if result.gad7_estimated_score > 0:
            severity = self._get_gad7_severity_label(result.gad7_estimated_score)
            parts.append(f"Anxiety indicators: {severity} (estimated GAD-7: {result.gad7_estimated_score})")
        
        # Specific markers
        if result.markers:
            marker_names = list(set(m.item_name for m in result.markers))
            parts.append(f"Detected: {', '.join(marker_names)}")
        
        # Protective factors
        if result.protective_factors:
            parts.append(f"Protective factors: {', '.join(result.protective_factors)}")
        
        if not parts:
            parts.append("No significant clinical indicators detected.")
        
        return " | ".join(parts)
    
    def _get_phq9_severity_label(self, score: int) -> str:
        """Get PHQ-9 severity label from score."""
        if score >= 20:
            return "severe"
        elif score >= 15:
            return "moderately severe"
        elif score >= 10:
            return "moderate"
        elif score >= 5:
            return "mild"
        else:
            return "minimal"
    
    def _get_gad7_severity_label(self, score: int) -> str:
        """Get GAD-7 severity label from score."""
        if score >= 15:
            return "severe"
        elif score >= 10:
            return "moderate"
        elif score >= 5:
            return "mild"
        else:
            return "minimal"
    
    def _calculate_confidence(self, result: SemanticAnalysisResult) -> float:
        """Calculate confidence in the analysis.
        
        Higher confidence when:
        - More markers detected
        - Markers from multiple frameworks
        - Clear severity patterns
        """
        if not result.markers:
            return 0.5  # Baseline confidence for no markers
        
        # More markers = higher confidence
        marker_confidence = min(1.0, len(result.markers) * 0.15)
        
        # Multiple frameworks = higher confidence
        frameworks = set(m.framework for m in result.markers)
        framework_bonus = 0.1 if len(frameworks) > 1 else 0
        
        # High severity markers = higher confidence
        high_severity = any(m.severity >= 3 for m in result.markers)
        severity_bonus = 0.1 if high_severity else 0
        
        return min(1.0, 0.5 + marker_confidence + framework_bonus + severity_bonus)
