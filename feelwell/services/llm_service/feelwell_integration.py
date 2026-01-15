"""Feelwell Service Integration for LLM.

Integrates the Safe LLM Service with existing Feelwell services:
- Safety Service (crisis detection, text normalization, semantic analysis)
- Audit Service (logging and compliance)
- Crisis Engine (event publishing)
- Observer Service (session tracking)

This module provides the glue code to connect the new LLM capabilities
with your existing production services while maintaining ADR compliance.
"""

import logging
import os
from typing import Optional, Dict
from dataclasses import dataclass

from .base_llm import create_llm, LLMConfig, LLMProvider
from .safe_llm_service import SafeLLMService, SafeResponse
from ..safety_service.scanner import CrisisScanner
from ..safety_service.text_normalizer import TextNormalizer
from ..safety_service.semantic_analyzer import SemanticAnalyzer
from ..audit_service.audit_logger import AuditLogger
from ..crisis_engine.handler import publish_crisis_event
from ...shared.models.risk import RiskLevel

logger = logging.getLogger(__name__)


@dataclass
class FeelwellLLMConfig:
    """Configuration for Feelwell LLM integration."""
    # LLM Configuration
    llm_provider: str = "huggingface"  # or "openai", "aws_sagemaker"
    model_name: str = "Mental-Health-FineTuned-Mistral-7B"
    model_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    
    # Feature Flags
    enable_llm: bool = True  # Master switch for LLM
    enable_crisis_bypass: bool = True  # ADR-001 compliance
    enable_audit_logging: bool = True  # ADR-005 compliance
    enable_crisis_publishing: bool = True  # ADR-004 compliance
    
    # Performance
    max_tokens: int = 512
    temperature: float = 0.7
    timeout_seconds: int = 30
    
    @classmethod
    def from_env(cls) -> 'FeelwellLLMConfig':
        """Create configuration from environment variables."""
        return cls(
            llm_provider=os.environ.get("LLM_PROVIDER", "huggingface"),
            model_name=os.environ.get("LLM_MODEL_NAME", "Mental-Health-FineTuned-Mistral-7B"),
            model_endpoint=os.environ.get("LLM_ENDPOINT"),
            api_key=os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("OPENAI_API_KEY"),
            enable_llm=os.environ.get("ENABLE_LLM", "true").lower() == "true",
            enable_crisis_bypass=os.environ.get("ENABLE_CRISIS_BYPASS", "true").lower() == "true",
            enable_audit_logging=os.environ.get("ENABLE_AUDIT_LOGGING", "true").lower() == "true",
            enable_crisis_publishing=os.environ.get("ENABLE_CRISIS_PUBLISHING", "true").lower() == "true",
        )


class FeelwellLLMService:
    """Integrated LLM service for Feelwell platform.
    
    This service orchestrates all LLM-related functionality while ensuring
    compliance with Feelwell's architectural decisions (ADRs).
    """
    
    def __init__(
        self,
        config: Optional[FeelwellLLMConfig] = None,
        crisis_scanner: Optional[CrisisScanner] = None,
        text_normalizer: Optional[TextNormalizer] = None,
        semantic_analyzer: Optional[SemanticAnalyzer] = None,
        audit_logger: Optional[AuditLogger] = None
    ):
        """Initialize Feelwell LLM Service.
        
        Args:
            config: LLM configuration (uses env vars if None)
            crisis_scanner: Crisis detection scanner (creates new if None)
            text_normalizer: Text normalization utility (creates new if None)
            semantic_analyzer: Semantic analysis service (creates new if None)
            audit_logger: Audit logging service (creates new if None)
        """
        self.config = config or FeelwellLLMConfig.from_env()
        
        # Initialize components
        self.crisis_scanner = crisis_scanner or CrisisScanner()
        self.text_normalizer = text_normalizer or TextNormalizer()
        self.semantic_analyzer = semantic_analyzer or SemanticAnalyzer()
        self.audit_logger = audit_logger or AuditLogger()
        
        # Initialize LLM if enabled
        self.safe_llm = None
        if self.config.enable_llm:
            self._initialize_llm()
        
        logger.info(
            "Feelwell LLM Service initialized",
            extra={
                "llm_enabled": self.config.enable_llm,
                "model": self.config.model_name,
                "provider": self.config.llm_provider
            }
        )
    
    def _initialize_llm(self):
        """Initialize the LLM and Safe LLM Service."""
        try:
            # Create LLM configuration
            llm_config = LLMConfig(
                provider=LLMProvider(self.config.llm_provider),
                model_name=self.config.model_name,
                endpoint=self.config.model_endpoint,
                api_key=self.config.api_key,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                timeout_seconds=self.config.timeout_seconds
            )
            
            # Create LLM instance
            llm = create_llm(llm_config)
            
            # Create Safe LLM Service (ADR-001 compliant)
            self.safe_llm = SafeLLMService(
                llm=llm,
                crisis_scanner=self.crisis_scanner,
                text_normalizer=self.text_normalizer,
                semantic_analyzer=self.semantic_analyzer
            )
            
            logger.info("LLM initialized successfully")
            
        except Exception as e:
            logger.error(
                "Failed to initialize LLM",
                extra={"error": str(e)}
            )
            # LLM will remain None, fallback responses will be used
    
    async def generate_response(
        self,
        student_id: str,
        message: str,
        conversation_history: Optional[list] = None,
        session_id: Optional[str] = None
    ) -> Dict:
        """Generate response for student message.
        
        This is the main entry point for Feelwell services to get LLM responses.
        It handles all safety checks, logging, and event publishing.
        
        Args:
            student_id: Student identifier (will be hashed for logging)
            message: Student's message
            conversation_history: Optional conversation context
            session_id: Optional session identifier
            
        Returns:
            Dictionary with response and metadata:
            {
                "text": str,
                "risk_level": str,
                "crisis_detected": bool,
                "source": str,
                "session_id": str,
                "metadata": dict
            }
        """
        logger.info(
            "RESPONSE_GENERATION_STARTED",
            extra={
                "student_id_hash": self._hash_student_id(student_id),
                "session_id": session_id,
                "message_length": len(message)
            }
        )
        
        try:
            # Generate safe response
            if self.safe_llm and self.config.enable_llm:
                safe_response = await self.safe_llm.generate_safe_response(
                    message=message,
                    student_id=student_id,
                    conversation_history=conversation_history
                )
            else:
                # Fallback if LLM not available
                safe_response = self._get_fallback_response(student_id, message)
            
            # Audit logging (ADR-005)
            if self.config.enable_audit_logging:
                await self._log_interaction(
                    student_id=student_id,
                    message=message,
                    response=safe_response,
                    session_id=session_id
                )
            
            # Crisis event publishing (ADR-004)
            if safe_response.crisis_detected and self.config.enable_crisis_publishing:
                await self._publish_crisis_event(
                    student_id=student_id,
                    response=safe_response,
                    session_id=session_id
                )
            
            # Format response for Feelwell services
            return {
                "text": safe_response.text,
                "risk_level": safe_response.risk_level.value,
                "crisis_detected": safe_response.crisis_detected,
                "source": safe_response.source.value,
                "llm_bypassed": safe_response.llm_bypassed,
                "session_id": session_id,
                "metadata": {
                    "student_id_hash": safe_response.student_id_hash,
                    "safety_checks_passed": safe_response.safety_checks_passed,
                    **safe_response.metadata
                }
            }
            
        except Exception as e:
            logger.error(
                "RESPONSE_GENERATION_FAILED",
                extra={
                    "student_id_hash": self._hash_student_id(student_id),
                    "error": str(e)
                }
            )
            
            # Return safe fallback
            return {
                "text": self._get_error_fallback_text(),
                "risk_level": RiskLevel.SAFE.value,
                "crisis_detected": False,
                "source": "fallback",
                "llm_bypassed": True,
                "session_id": session_id,
                "metadata": {"error": str(e)}
            }
    
    async def _log_interaction(
        self,
        student_id: str,
        message: str,
        response: SafeResponse,
        session_id: Optional[str]
    ):
        """Log interaction to audit trail (ADR-005).
        
        Args:
            student_id: Student identifier
            message: Student's message
            response: Safe response object
            session_id: Session identifier
        """
        try:
            await self.audit_logger.log_interaction(
                student_id_hash=response.student_id_hash,
                session_id=session_id,
                message_hash=self._hash_message(message),
                risk_level=response.risk_level.value,
                crisis_detected=response.crisis_detected,
                llm_bypassed=response.llm_bypassed,
                response_source=response.source.value,
                metadata=response.metadata
            )
            
            logger.info(
                "INTERACTION_LOGGED",
                extra={
                    "student_id_hash": response.student_id_hash,
                    "session_id": session_id
                }
            )
            
        except Exception as e:
            logger.error(
                "AUDIT_LOGGING_FAILED",
                extra={
                    "student_id_hash": response.student_id_hash,
                    "error": str(e)
                }
            )
    
    async def _publish_crisis_event(
        self,
        student_id: str,
        response: SafeResponse,
        session_id: Optional[str]
    ):
        """Publish crisis event to EventBridge/Kafka (ADR-004).
        
        Args:
            student_id: Student identifier
            response: Safe response object
            session_id: Session identifier
        """
        try:
            await publish_crisis_event(
                student_id_hash=response.student_id_hash,
                session_id=session_id,
                crisis_type=response.metadata.get("crisis_type", "unknown"),
                risk_level=response.risk_level.value,
                keywords_matched=response.metadata.get("keywords_matched", [])
            )
            
            logger.critical(
                "CRISIS_EVENT_PUBLISHED",
                extra={
                    "student_id_hash": response.student_id_hash,
                    "crisis_type": response.metadata.get("crisis_type"),
                    "session_id": session_id
                }
            )
            
        except Exception as e:
            logger.critical(
                "CRISIS_EVENT_PUBLISHING_FAILED",
                extra={
                    "student_id_hash": response.student_id_hash,
                    "error": str(e)
                }
            )
    
    def _get_fallback_response(
        self,
        student_id: str,
        message: str
    ) -> SafeResponse:
        """Get fallback response when LLM not available.
        
        Args:
            student_id: Student identifier
            message: Student's message
            
        Returns:
            SafeResponse with fallback text
        """
        from ...shared.utils.pii import hash_pii
        
        return SafeResponse(
            text=self._get_error_fallback_text(),
            source="fallback",
            risk_level=RiskLevel.SAFE,
            crisis_detected=False,
            safety_checks_passed=True,
            llm_bypassed=True,
            student_id_hash=hash_pii(student_id)
        )
    
    def _get_error_fallback_text(self) -> str:
        """Get fallback text for errors."""
        return """I'm here to support you. I want to make sure you get the best help possible.

I'd encourage you to speak with your school counselor - they're trained to help with situations like this and they care about your wellbeing.

If you need immediate support, you can also reach out to:
• Crisis Text Line: Text HOME to 741741 (24/7)
• National Suicide Prevention Lifeline: 988

You don't have to go through this alone."""
    
    def _hash_student_id(self, student_id: str) -> str:
        """Hash student ID for logging (ADR-003)."""
        from ...shared.utils.pii import hash_pii
        return hash_pii(student_id)
    
    def _hash_message(self, message: str) -> str:
        """Hash message for audit logging."""
        import hashlib
        return hashlib.sha256(message.encode()).hexdigest()[:16]
    
    def health_check(self) -> Dict:
        """Check health of LLM service.
        
        Returns:
            Dictionary with health status
        """
        return {
            "llm_enabled": self.config.enable_llm,
            "llm_available": self.safe_llm is not None,
            "model": self.config.model_name,
            "provider": self.config.llm_provider,
            "crisis_bypass_enabled": self.config.enable_crisis_bypass,
            "audit_logging_enabled": self.config.enable_audit_logging,
            "crisis_publishing_enabled": self.config.enable_crisis_publishing
        }


# Singleton instance for easy import
_feelwell_llm_service: Optional[FeelwellLLMService] = None


def get_feelwell_llm_service() -> FeelwellLLMService:
    """Get singleton instance of Feelwell LLM Service.
    
    Returns:
        FeelwellLLMService instance
    """
    global _feelwell_llm_service
    
    if _feelwell_llm_service is None:
        _feelwell_llm_service = FeelwellLLMService()
    
    return _feelwell_llm_service


async def generate_student_response(
    student_id: str,
    message: str,
    conversation_history: Optional[list] = None,
    session_id: Optional[str] = None
) -> Dict:
    """Convenience function for generating student responses.
    
    This is the recommended way to use the LLM service from other Feelwell services.
    
    Args:
        student_id: Student identifier
        message: Student's message
        conversation_history: Optional conversation context
        session_id: Optional session identifier
        
    Returns:
        Dictionary with response and metadata
    """
    service = get_feelwell_llm_service()
    return await service.generate_response(
        student_id=student_id,
        message=message,
        conversation_history=conversation_history,
        session_id=session_id
    )
