"""BERT-based sentiment analyzer for Observer Service.

Provides ML-based sentiment analysis as a secondary layer to
complement the regex-based clinical marker detection.

Note: BERT adds ~100-200ms latency. Only enable if acceptable for SLA.
For CPU-only inference (Fargate), we use DistilBERT for speed.
"""
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SentimentLabel(Enum):
    """Sentiment classification labels."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class SentimentResult:
    """Result of sentiment analysis."""
    label: SentimentLabel
    confidence: float  # 0.0 to 1.0
    risk_contribution: float  # How much this adds to risk score (-0.5 to 0.5)
    model_name: str
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")
        if not -0.5 <= self.risk_contribution <= 0.5:
            raise ValueError(f"Risk contribution must be -0.5-0.5, got {self.risk_contribution}")


class BERTSentimentAnalyzer:
    """BERT-based sentiment analyzer using HuggingFace Transformers.
    
    Uses DistilBERT for faster inference on CPU (Fargate).
    Falls back gracefully if model loading fails.
    """
    
    # Model configuration
    DEFAULT_MODEL = "distilbert-base-uncased-finetuned-sst-2-english"
    MAX_LENGTH = 512  # BERT max token length
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        enabled: bool = True,
        device: str = "cpu",
    ):
        """Initialize BERT sentiment analyzer.
        
        Args:
            model_name: HuggingFace model name (default: DistilBERT SST-2)
            enabled: Whether to enable BERT analysis
            device: Device for inference ("cpu" or "cuda")
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.enabled = enabled
        self.device = device
        self._pipeline = None
        self._initialized = False
        self._init_error: Optional[str] = None
        
        if enabled:
            self._initialize_model()
    
    def _initialize_model(self) -> None:
        """Lazy initialization of the sentiment pipeline."""
        if self._initialized:
            return
        
        try:
            from transformers import pipeline
            
            logger.info(
                "BERT_MODEL_LOADING",
                extra={"model_name": self.model_name, "device": self.device}
            )
            
            self._pipeline = pipeline(
                "sentiment-analysis",
                model=self.model_name,
                device=-1 if self.device == "cpu" else 0,  # -1 for CPU
                truncation=True,
                max_length=self.MAX_LENGTH,
            )
            
            self._initialized = True
            logger.info(
                "BERT_MODEL_LOADED",
                extra={"model_name": self.model_name}
            )
            
        except ImportError as e:
            self._init_error = f"transformers not installed: {e}"
            logger.warning(
                "BERT_IMPORT_ERROR",
                extra={"error": self._init_error}
            )
            self.enabled = False
            
        except Exception as e:
            self._init_error = str(e)
            logger.error(
                "BERT_INIT_ERROR",
                extra={"error": self._init_error, "model_name": self.model_name}
            )
            self.enabled = False
    
    def analyze(self, text: str) -> SentimentResult:
        """Analyze sentiment of text using BERT.
        
        Args:
            text: Text to analyze (will be truncated to MAX_LENGTH tokens)
            
        Returns:
            SentimentResult with label, confidence, and risk contribution
        """
        if not self.enabled or self._pipeline is None:
            return self._fallback_result()
        
        try:
            # Truncate text for BERT
            truncated = text[:2000]  # Rough char limit before tokenization
            
            result = self._pipeline(truncated)[0]
            
            label_str = result["label"].upper()
            confidence = result["score"]
            
            # Map HuggingFace labels to our enum
            if label_str == "POSITIVE":
                label = SentimentLabel.POSITIVE
            elif label_str == "NEGATIVE":
                label = SentimentLabel.NEGATIVE
            else:
                label = SentimentLabel.NEUTRAL
            
            # Calculate risk contribution based on sentiment
            risk_contribution = self._calculate_risk_contribution(label, confidence)
            
            logger.debug(
                "BERT_ANALYSIS_COMPLETE",
                extra={
                    "label": label.value,
                    "confidence": confidence,
                    "risk_contribution": risk_contribution,
                }
            )
            
            return SentimentResult(
                label=label,
                confidence=confidence,
                risk_contribution=risk_contribution,
                model_name=self.model_name,
            )
            
        except Exception as e:
            logger.error(
                "BERT_ANALYSIS_ERROR",
                extra={"error": str(e)}
            )
            return self._fallback_result()
    
    def _calculate_risk_contribution(
        self, 
        label: SentimentLabel, 
        confidence: float
    ) -> float:
        """Calculate risk contribution from sentiment.
        
        Negative sentiment with high confidence increases risk.
        Positive sentiment slightly decreases risk.
        
        Args:
            label: Sentiment label
            confidence: Model confidence
            
        Returns:
            Risk contribution (0.0 to 0.5)
        """
        if label == SentimentLabel.NEGATIVE:
            # High confidence negative = higher risk
            if confidence >= 0.95:
                return 0.4
            elif confidence >= 0.85:
                return 0.3
            elif confidence >= 0.7:
                return 0.2
            else:
                return 0.1
        elif label == SentimentLabel.POSITIVE:
            # Positive sentiment slightly reduces risk
            if confidence >= 0.9:
                return -0.1  # Negative contribution = risk reduction
            return 0.0
        else:
            return 0.0
    
    def _fallback_result(self) -> SentimentResult:
        """Return neutral result when BERT is unavailable."""
        return SentimentResult(
            label=SentimentLabel.NEUTRAL,
            confidence=0.5,
            risk_contribution=0.0,
            model_name="fallback",
        )
    
    @property
    def is_available(self) -> bool:
        """Check if BERT analyzer is available and initialized."""
        return self.enabled and self._initialized and self._pipeline is not None
    
    def get_status(self) -> dict:
        """Get analyzer status for health checks."""
        return {
            "enabled": self.enabled,
            "initialized": self._initialized,
            "model_name": self.model_name,
            "device": self.device,
            "error": self._init_error,
        }
