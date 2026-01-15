"""Pattern analyzer for longitudinal risk detection.

Uses RAG to retrieve relevant historical context and
identify patterns across student sessions over time.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from .vector_store import VectorStore, Document, SearchResult

logger = logging.getLogger(__name__)


class RiskPattern(Enum):
    """Identified risk patterns."""
    ESCALATING = "escalating"
    CHRONIC = "chronic"
    CYCLICAL = "cyclical"
    ACUTE = "acute"
    IMPROVING = "improving"
    STABLE = "stable"


@dataclass
class PatternMatch:
    """A matched pattern with supporting evidence."""
    pattern: RiskPattern
    confidence: float
    supporting_sessions: List[str]
    risk_trajectory: List[float]
    recommendation: str


@dataclass
class ContextWindow:
    """Retrieved context for analysis."""
    documents: List[Document]
    relevance_scores: List[float]
    time_span_days: int
    session_count: int


class PatternAnalyzer:
    """Analyzes patterns from retrieved historical context."""
    
    def __init__(self, vector_store: VectorStore):
        """Initialize analyzer.
        
        Args:
            vector_store: Vector store for context retrieval
        """
        self.vector_store = vector_store
        logger.info("PATTERN_ANALYZER_INITIALIZED")
    
    def get_context_window(
        self,
        student_id_hash: str,
        query: Optional[str] = None,
        max_sessions: int = 20,
    ) -> ContextWindow:
        """Retrieve context window for a student.
        
        Args:
            student_id_hash: Hashed student identifier
            query: Optional query for semantic search
            max_sessions: Maximum sessions to retrieve
            
        Returns:
            ContextWindow with relevant documents
        """
        if query:
            # Semantic search
            results = self.vector_store.search(
                query=query,
                student_id_hash=student_id_hash,
                top_k=max_sessions,
            )
            documents = [r.document for r in results]
            relevance_scores = [r.similarity_score for r in results]
        else:
            # Get all history
            documents = self.vector_store.get_student_history(
                student_id_hash=student_id_hash,
                limit=max_sessions,
            )
            relevance_scores = [1.0] * len(documents)
        
        # Calculate time span
        if documents:
            timestamps = [d.created_at for d in documents]
            time_span = (max(timestamps) - min(timestamps)).days
        else:
            time_span = 0
        
        return ContextWindow(
            documents=documents,
            relevance_scores=relevance_scores,
            time_span_days=time_span,
            session_count=len(documents),
        )
    
    def analyze_pattern(
        self,
        context: ContextWindow,
    ) -> PatternMatch:
        """Analyze pattern from context window.
        
        Args:
            context: Retrieved context window
            
        Returns:
            PatternMatch with identified pattern
        """
        if not context.documents:
            return PatternMatch(
                pattern=RiskPattern.STABLE,
                confidence=0.5,
                supporting_sessions=[],
                risk_trajectory=[],
                recommendation="Insufficient data for pattern analysis",
            )
        
        # Extract risk trajectory
        risk_trajectory = [
            doc.metadata.get("risk_score", 0.3)
            for doc in context.documents
        ]
        
        session_ids = [doc.session_id or doc.doc_id for doc in context.documents]
        
        # Analyze trajectory
        pattern, confidence = self._classify_pattern(risk_trajectory)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(pattern, risk_trajectory)
        
        return PatternMatch(
            pattern=pattern,
            confidence=confidence,
            supporting_sessions=session_ids,
            risk_trajectory=risk_trajectory,
            recommendation=recommendation,
        )
    
    def _classify_pattern(
        self,
        trajectory: List[float],
    ) -> tuple:
        """Classify pattern from risk trajectory.
        
        Returns:
            Tuple of (RiskPattern, confidence)
        """
        if len(trajectory) < 2:
            return RiskPattern.STABLE, 0.5
        
        # Calculate trend
        n = len(trajectory)
        x_mean = (n - 1) / 2
        y_mean = sum(trajectory) / n
        
        numerator = sum((i - x_mean) * (trajectory[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        slope = numerator / denominator if denominator != 0 else 0
        
        # Calculate variance for cyclical detection
        import statistics
        variance = statistics.variance(trajectory) if len(trajectory) > 1 else 0
        
        # Check for acute spike
        max_risk = max(trajectory)
        if max_risk >= 0.8 and trajectory[-1] >= 0.7:
            return RiskPattern.ACUTE, 0.85
        
        # Classify by slope and variance
        if slope > 0.03:
            return RiskPattern.ESCALATING, min(0.9, 0.6 + abs(slope) * 3)
        elif slope < -0.03:
            return RiskPattern.IMPROVING, min(0.9, 0.6 + abs(slope) * 3)
        elif variance > 0.03:
            return RiskPattern.CYCLICAL, min(0.8, 0.5 + variance * 5)
        elif y_mean > 0.4:
            return RiskPattern.CHRONIC, 0.7
        else:
            return RiskPattern.STABLE, 0.75
    
    def _generate_recommendation(
        self,
        pattern: RiskPattern,
        trajectory: List[float],
    ) -> str:
        """Generate intervention recommendation."""
        recent_risk = trajectory[-1] if trajectory else 0.3
        
        recommendations = {
            RiskPattern.ACUTE: "URGENT: Immediate crisis intervention required. "
                              "Activate crisis protocol and ensure student safety.",
            RiskPattern.ESCALATING: "Schedule proactive counselor outreach within 24-48 hours. "
                                   "Risk trajectory shows concerning upward trend.",
            RiskPattern.CHRONIC: "Consider referral to ongoing support services. "
                                "Persistent elevated risk indicates need for sustained intervention.",
            RiskPattern.CYCLICAL: "Identify triggers for cyclical patterns. "
                                 "Schedule check-ins during historically high-risk periods.",
            RiskPattern.IMPROVING: "Continue current support approach. "
                                  "Monitor for potential relapse.",
            RiskPattern.STABLE: "Maintain standard monitoring. "
                               "No immediate intervention indicated.",
        }
        
        base_rec = recommendations.get(pattern, "Continue monitoring.")
        
        # Add urgency based on recent risk
        if recent_risk >= 0.7:
            base_rec = "⚠️ HIGH RECENT RISK. " + base_rec
        
        return base_rec
    
    def find_similar_cases(
        self,
        query_text: str,
        exclude_student: Optional[str] = None,
        top_k: int = 5,
    ) -> List[SearchResult]:
        """Find similar cases across all students.
        
        Useful for identifying students with similar presentations.
        
        Args:
            query_text: Text to search for
            exclude_student: Student to exclude from results
            top_k: Number of results
            
        Returns:
            List of similar cases
        """
        results = self.vector_store.search(
            query=query_text,
            top_k=top_k * 2,  # Get extra to filter
        )
        
        # Filter out excluded student
        if exclude_student:
            results = [
                r for r in results
                if r.document.student_id_hash != exclude_student
            ]
        
        return results[:top_k]
