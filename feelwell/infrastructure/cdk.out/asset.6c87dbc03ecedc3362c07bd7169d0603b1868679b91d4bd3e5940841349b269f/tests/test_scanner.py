"""Tests for SafetyScanner - safety-critical code requires 100% coverage.

These tests include adversarial cases to ensure the scanner catches
crisis language even when disguised or encoded.
"""
import pytest
from unittest.mock import patch

from feelwell.shared.models import RiskLevel
from feelwell.shared.utils import configure_pii_salt
from feelwell.services.safety_service.scanner import SafetyScanner, ScanResult
from feelwell.services.safety_service.config import SafetyConfig, ClinicalThresholds


@pytest.fixture(autouse=True)
def setup_pii_salt():
    """Configure PII salt before each test."""
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def scanner():
    """Create a SafetyScanner instance for testing."""
    return SafetyScanner()


class TestSafeMessage:
    """Tests for messages that should pass safely."""
    
    def test_normal_message_returns_safe(self, scanner):
        """Normal conversation should return SAFE risk level."""
        result = scanner.scan(
            message_id="msg_001",
            text="I had a good day at school today",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.SAFE
        assert result.bypass_llm is False
        assert result.risk_score < 0.3
        assert len(result.matched_keywords) == 0
    
    def test_exam_stress_returns_safe(self, scanner):
        """Exam stress without crisis language should be SAFE."""
        result = scanner.scan(
            message_id="msg_002",
            text="I'm stressed about my math exam tomorrow",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.SAFE
        assert result.bypass_llm is False
    
    def test_empty_message(self, scanner):
        """Empty message should return SAFE."""
        result = scanner.scan(
            message_id="msg_003",
            text="",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.SAFE
        assert result.bypass_llm is False


class TestCautionMessage:
    """Tests for messages that should trigger CAUTION level."""
    
    def test_single_caution_keyword(self, scanner):
        """Single caution keyword should elevate risk."""
        result = scanner.scan(
            message_id="msg_010",
            text="I feel so hopeless about everything",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CAUTION
        assert result.bypass_llm is False
        assert "hopeless" in result.matched_keywords
    
    def test_multiple_caution_keywords(self, scanner):
        """Multiple caution keywords should increase risk score."""
        result = scanner.scan(
            message_id="msg_011",
            text="I feel worthless and alone, nobody cares about me",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CAUTION
        assert result.bypass_llm is False
        assert len(result.matched_keywords) >= 2
        assert result.risk_score >= 0.4


class TestCrisisMessage:
    """Tests for messages that should trigger CRISIS and LLM bypass."""
    
    def test_explicit_suicide_mention(self, scanner):
        """Explicit suicide mention must trigger crisis bypass."""
        result = scanner.scan(
            message_id="msg_020",
            text="I want to kill myself",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
        assert result.risk_score == 1.0
    
    def test_method_mention_pills(self, scanner):
        """Mention of method (pills) must trigger crisis."""
        result = scanner.scan(
            message_id="msg_021",
            text="I've been thinking about taking all my pills",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_method_mention_bridge(self, scanner):
        """Mention of method (bridge) must trigger crisis."""
        result = scanner.scan(
            message_id="msg_022",
            text="I keep thinking about the bridge near my house",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_coded_language_unalive(self, scanner):
        """Teen slang 'unalive' must trigger crisis."""
        result = scanner.scan(
            message_id="msg_023",
            text="I want to unalive myself",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_coded_language_ghost(self, scanner):
        """Coded language 'become a ghost' must trigger crisis."""
        result = scanner.scan(
            message_id="msg_024",
            text="Sometimes I think about becoming a ghost",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_goodbye_forever(self, scanner):
        """'Goodbye forever' must trigger crisis."""
        result = scanner.scan(
            message_id="msg_025",
            text="I just wanted to say goodbye forever to everyone",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_self_harm_cutting(self, scanner):
        """Self-harm language must trigger crisis."""
        result = scanner.scan(
            message_id="msg_026",
            text="I've been cutting myself again",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True


class TestAdversarialCases:
    """Adversarial tests - attempts to bypass safety detection."""
    
    def test_case_insensitive_detection(self, scanner):
        """Crisis keywords should be detected regardless of case."""
        result = scanner.scan(
            message_id="msg_030",
            text="I want to KILL MYSELF",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_mixed_case_detection(self, scanner):
        """Mixed case should still be detected."""
        result = scanner.scan(
            message_id="msg_031",
            text="I want to KiLl MySeLf",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_extra_whitespace(self, scanner):
        """Extra whitespace should not prevent detection."""
        result = scanner.scan(
            message_id="msg_032",
            text="   I want to kill myself   ",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True
    
    def test_word_boundary_prevents_false_positive(self, scanner):
        """'cut' should not match 'cute'."""
        result = scanner.scan(
            message_id="msg_033",
            text="My cat is so cute",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.SAFE
        assert result.bypass_llm is False
    
    def test_psychosis_indicator(self, scanner):
        """Psychosis indicators must trigger crisis."""
        result = scanner.scan(
            message_id="msg_034",
            text="The voices telling me to do things won't stop",
            student_id="student_123",
        )
        
        assert result.risk_level == RiskLevel.CRISIS
        assert result.bypass_llm is True


class TestScanMetadata:
    """Tests for scan result metadata."""
    
    def test_scan_latency_recorded(self, scanner):
        """Scan latency should be recorded."""
        result = scanner.scan(
            message_id="msg_040",
            text="Hello",
            student_id="student_123",
        )
        
        assert result.scan_latency_ms >= 0
        assert result.scan_latency_ms < 100  # Should be fast
    
    def test_scanner_version_recorded(self, scanner):
        """Scanner version should be recorded for audit."""
        result = scanner.scan(
            message_id="msg_041",
            text="Hello",
            student_id="student_123",
        )
        
        assert result.scanner_version != ""
    
    def test_message_id_preserved(self, scanner):
        """Message ID should be preserved in result."""
        result = scanner.scan(
            message_id="msg_042",
            text="Hello",
            student_id="student_123",
        )
        
        assert result.message_id == "msg_042"


class TestConfigurability:
    """Tests for scanner configuration."""
    
    def test_custom_thresholds(self):
        """Scanner should respect custom thresholds."""
        custom_thresholds = ClinicalThresholds(
            LOW_SEVERITY_MAX=0.2,
            MODERATE_SEVERITY_MAX=0.5,
        )
        scanner = SafetyScanner(thresholds=custom_thresholds)
        
        result = scanner.scan(
            message_id="msg_050",
            text="I feel hopeless",
            student_id="student_123",
        )
        
        # With lower thresholds, this should be CAUTION
        assert result.risk_level == RiskLevel.CAUTION
