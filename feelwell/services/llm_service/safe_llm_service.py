"""Safe LLM Service with Deterministic Guardrails.

Implements ADR-001: Safety checks MUST run before LLM calls.
Crisis keywords trigger immediate bypass of LLM.

This service integrates LLM capabilities with Feelwell's safety-first architecture,
ensuring that deterministic safety guardrails always take precedence over AI responses.
"""

import logging
from typing import Optional, Dict
from dataclasses import dataclass
from enum import Enum

from ...shared.models.risk import RiskLevel
from ...shared.utils.pii import hash_pii
from ..safety_service.scanner import CrisisScanner
from ..safety_service.text_normalizer import TextNormalizer
from ..safety_service.semantic_analyzer import SemanticAnalyzer
from .base_llm import BaseLLM, LLMResponse

logger = logging.getLogger(__name__)


class ResponseSource(Enum):
    """Source of the response."""
    CRISIS_PROTOCOL = "crisis_protocol"  # Deterministic crisis response
    SAFETY_GUARDRAIL = "safety_guardrail"  # Deterministic safety response
    LLM_GENERATED = "llm_generated"  # LLM-generated response
    FALLBACK = "fallback"  # Fallback response on error


@dataclass
class SafeResponse:
    """Response from Safe LLM Service with safety metadata."""
    text: str
    source: ResponseSource
    risk_level: RiskLevel
    crisis_detected: bool
    safety_checks_passed: bool
    llm_bypassed: bool
    student_id_hash: str
    metadata: Optional[Dict] = None


class SafeLLMService:
    """LLM service with integrated safety guardrails (ADR-001 compliant)."""
    
    # Deterministic crisis responses (bypass LLM)
    CRISIS_RESPONSES = {
        "suicide": """I'm really concerned about what you've shared with me. Your safety is the most important thing right now.

I need you to know that you don't have to face this alone. Please reach out to someone who can help immediately:

• **National Suicide Prevention Lifeline**: 988 (call or text, 24/7)
• **Crisis Text Line**: Text HOME to 741741
• **School Counselor**: Available during school hours
• **Emergency Services**: Call 911 if you're in immediate danger

I'm also notifying your school counselor right now so they can provide you with immediate support. They care about you and want to help.

You matter, and there are people who want to support you through this difficult time.""",
        
        "self_harm": """I'm concerned about what you've shared. Hurting yourself is a sign that you're dealing with very difficult emotions, and I want to make sure you get the support you need.

Please reach out to someone who can help:

• **Crisis Text Line**: Text HOME to 741741 (24/7)
• **School Counselor**: Available during school hours
• **National Suicide Prevention Lifeline**: 988

I'm notifying your school counselor so they can check in with you and provide support. They're trained to help with situations like this and they care about your wellbeing.

You don't have to go through this alone.""",
        
        "abuse": """Thank you for trusting me with this information. What you've described sounds very serious, and I want to make sure you're safe.

If you're in immediate danger, please:
• **Call 911** for emergency help
• **Go to a trusted adult** (teacher, counselor, family member)

I'm required to report this to your school counselor to ensure you get the help and protection you need. This is to keep you safe, not to get you in trouble.

Resources available:
• **Childhelp National Child Abuse Hotline**: 1-800-422-4453 (24/7)
• **School Counselor**: Available during school hours

You did the right thing by reaching out."""
    }
    
    def __init__(
        self,
        llm: BaseLLM,
        crisis_scanner: CrisisScanner,
        text_normalizer: TextNormalizer,
        semantic_analyzer: SemanticAnalyzer
    ):
        """Initialize Safe LLM Service.
        
        Args:
            llm: LLM instance for generating responses
            crisis_scanner: Deterministic crisis detection scanner
            text_normalizer: Text normalization utility
            semantic_analyzer: Semantic analysis for risk assessment
        """
        self.llm = llm
        self.crisis_scanner = crisis_scanner
        self.text_normalizer = text_normalizer
        self.semantic_analyzer = semantic_analyzer
        
        logger.info("Safe LLM Service initialized (ADR-001 compliant)")
    
    async def generate_safe_response(
        self,
        message: str,
        student_id: str,
        conversation_history: Optional[list] = None
    ) -> SafeResponse:
        """Generate response with safety-first approach (ADR-001).
        
        CRITICAL: Safety checks run BEFORE LLM inference.
        Crisis detection bypasses LLM entirely.
        
        Args:
            message: Student's message
            student_id: Student identifier (will be hashed for logging)
            conversation_history: Optional conversation context
            
        Returns:
            SafeResponse with safety metadata
        """
        student_id_hash = hash_pii(student_id)
        
        logger.info(
            "SAFE_LLM_REQUEST_STARTED",
            extra={
                "student_id_hash": student_id_hash,
                "message_length": len(message)
            }
        )
        
        # Step 1: Text Normalization
        normalized_message = self.text_normalizer.normalize(message)
        
        # Step 2: DETERMINISTIC CRISIS DETECTION (ADR-001)
        # This MUST run before LLM and bypass it if crisis detected
        crisis_result = self.crisis_scanner.scan(normalized_message)
        
        if crisis_result.is_crisis:
            logger.critical(
                "CRISIS_DETECTED_LLM_BYPASSED",
                extra={
                    "student_id_hash": student_id_hash,
                    "crisis_type": crisis_result.crisis_type,
                    "keywords_matched": crisis_result.keywords_matched
                }
            )
            
            # Return deterministic crisis response (NO LLM)
            crisis_response = self._get_crisis_response(crisis_result.crisis_type)
            
            return SafeResponse(
                text=crisis_response,
                source=ResponseSource.CRISIS_PROTOCOL,
                risk_level=RiskLevel.CRISIS,
                crisis_detected=True,
                safety_checks_passed=True,
                llm_bypassed=True,
                student_id_hash=student_id_hash,
                metadata={
                    "crisis_type": crisis_result.crisis_type,
                    "keywords_matched": crisis_result.keywords_matched
                }
            )
        
        # Step 3: Semantic Analysis for Risk Level
        semantic_result = self.semantic_analyzer.analyze(
            normalized_message,
            conversation_history
        )
        
        risk_level = semantic_result.risk_level
        
        logger.info(
            "SAFETY_CHECKS_PASSED",
            extra={
                "student_id_hash": student_id_hash,
                "risk_level": risk_level.value
            }
        )
        
        # Step 4: Generate LLM Response (only if safe)
        try:
            system_prompt = self._create_system_prompt(risk_level)
            
            llm_response = await self.llm.generate(
                prompt=message,
                system_prompt=system_prompt
            )
            
            # Step 5: Post-generation safety check
            if not self._validate_llm_response(llm_response.text):
                logger.warning(
                    "LLM_RESPONSE_FAILED_SAFETY_CHECK",
                    extra={"student_id_hash": student_id_hash}
                )
                return self._get_fallback_response(
                    student_id_hash,
                    risk_level
                )
            
            logger.info(
                "LLM_RESPONSE_GENERATED",
                extra={
                    "student_id_hash": student_id_hash,
                    "latency_ms": llm_response.latency_ms,
                    "tokens_used": llm_response.tokens_used
                }
            )
            
            return SafeResponse(
                text=llm_response.text,
                source=ResponseSource.LLM_GENERATED,
                risk_level=risk_level,
                crisis_detected=False,
                safety_checks_passed=True,
                llm_bypassed=False,
                student_id_hash=student_id_hash,
                metadata={
                    "model": llm_response.model,
                    "latency_ms": llm_response.latency_ms,
                    "tokens_used": llm_response.tokens_used
                }
            )
            
        except Exception as e:
            logger.error(
                "LLM_GENERATION_FAILED",
                extra={
                    "student_id_hash": student_id_hash,
                    "error": str(e)
                }
            )
            
            # Return safe fallback response
            return self._get_fallback_response(student_id_hash, risk_level)
    
    def _get_crisis_response(self, crisis_type: str) -> str:
        """Get deterministic crisis response.
        
        Args:
            crisis_type: Type of crisis detected
            
        Returns:
            Pre-defined crisis response text
        """
        return self.CRISIS_RESPONSES.get(
            crisis_type,
            self.CRISIS_RESPONSES["suicide"]  # Default to most serious
        )
    
    def _create_system_prompt(self, risk_level: RiskLevel) -> str:
        """Create system prompt based on risk level.
        
        Args:
            risk_level: Assessed risk level
            
        Returns:
            System prompt for LLM
        """
        base_prompt = """You are a helpful and empathetic mental health support assistant for students. Your role is to:

1. Listen actively and validate their feelings
2. Provide supportive, age-appropriate guidance
3. Encourage healthy coping strategies
4. Recommend speaking with school counselors or trusted adults when appropriate
5. NEVER provide medical advice or diagnoses
6. NEVER encourage harmful behaviors

Remember: You are a supportive resource, not a replacement for professional mental health care."""
        
        if risk_level == RiskLevel.CAUTION:
            base_prompt += """

IMPORTANT: This student may be experiencing elevated distress. Be extra supportive and gently encourage them to speak with their school counselor or a trusted adult."""
        
        return base_prompt
    
    def _validate_llm_response(self, response: str) -> bool:
        """Validate LLM response for safety.
        
        Args:
            response: LLM-generated response
            
        Returns:
            True if safe, False otherwise
        """
        # Check for harmful content
        harmful_patterns = [
            "kill yourself",
            "end your life",
            "you should die",
            "harm yourself",
            "commit suicide"
        ]
        
        response_lower = response.lower()
        
        for pattern in harmful_patterns:
            if pattern in response_lower:
                logger.critical(
                    "HARMFUL_CONTENT_IN_LLM_RESPONSE",
                    extra={"pattern": pattern}
                )
                return False
        
        # Check for medical advice (not allowed)
        medical_patterns = [
            "i diagnose",
            "you have depression",
            "you have anxiety disorder",
            "take this medication",
            "stop taking your medication"
        ]
        
        for pattern in medical_patterns:
            if pattern in response_lower:
                logger.warning(
                    "MEDICAL_ADVICE_IN_LLM_RESPONSE",
                    extra={"pattern": pattern}
                )
                return False
        
        return True
    
    def _get_fallback_response(
        self,
        student_id_hash: str,
        risk_level: RiskLevel
    ) -> SafeResponse:
        """Get safe fallback response when LLM fails.
        
        Args:
            student_id_hash: Hashed student ID
            risk_level: Assessed risk level
            
        Returns:
            SafeResponse with fallback text
        """
        fallback_text = """I'm here to support you. I want to make sure you get the best help possible.

I'd encourage you to speak with your school counselor - they're trained to help with situations like this and they care about your wellbeing.

If you need immediate support, you can also reach out to:
• Crisis Text Line: Text HOME to 741741 (24/7)
• National Suicide Prevention Lifeline: 988

You don't have to go through this alone."""
        
        logger.info(
            "FALLBACK_RESPONSE_USED",
            extra={"student_id_hash": student_id_hash}
        )
        
        return SafeResponse(
            text=fallback_text,
            source=ResponseSource.FALLBACK,
            risk_level=risk_level,
            crisis_detected=False,
            safety_checks_passed=True,
            llm_bypassed=True,
            student_id_hash=student_id_hash
        )
