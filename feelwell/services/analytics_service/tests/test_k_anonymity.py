"""Tests for k-anonymity enforcement per ADR-006."""
import pytest

from feelwell.services.analytics_service.k_anonymity import (
    KAnonymityEnforcer,
    AggregateResult,
    enforce_k_anonymity,
    K_ANONYMITY_THRESHOLD,
)


@pytest.fixture
def enforcer():
    """Create a KAnonymityEnforcer instance."""
    return KAnonymityEnforcer()


class TestKAnonymityThreshold:
    """Tests for k-anonymity threshold enforcement."""
    
    def test_group_below_threshold_suppressed(self, enforcer):
        """Groups with fewer than k members should be suppressed."""
        result = enforcer.check_and_suppress(
            data={"avg_risk": 0.5},
            group_size=3,
            context="test_query",
        )
        
        assert result.suppressed is True
        assert result.data is None
        assert result.group_size == 3
        assert "below" in result.suppression_reason.lower()
    
    def test_group_at_threshold_passes(self, enforcer):
        """Groups with exactly k members should pass."""
        result = enforcer.check_and_suppress(
            data={"avg_risk": 0.5},
            group_size=5,
            context="test_query",
        )
        
        assert result.suppressed is False
        assert result.data == {"avg_risk": 0.5}
    
    def test_group_above_threshold_passes(self, enforcer):
        """Groups with more than k members should pass."""
        result = enforcer.check_and_suppress(
            data={"avg_risk": 0.5},
            group_size=100,
            context="test_query",
        )
        
        assert result.suppressed is False
        assert result.data == {"avg_risk": 0.5}
    
    def test_single_student_suppressed(self, enforcer):
        """Single student data must always be suppressed."""
        result = enforcer.check_and_suppress(
            data={"student_risk": 0.8},
            group_size=1,
            context="individual_query",
        )
        
        assert result.suppressed is True
        assert result.data is None
    
    def test_default_threshold_is_five(self):
        """Default k-anonymity threshold should be 5."""
        assert K_ANONYMITY_THRESHOLD == 5


class TestCustomThreshold:
    """Tests for custom k-anonymity thresholds."""
    
    def test_custom_threshold_respected(self):
        """Custom threshold should be respected."""
        enforcer = KAnonymityEnforcer(k_threshold=10)
        
        # Group of 7 should be suppressed with k=10
        result = enforcer.check_and_suppress(
            data={"avg_risk": 0.5},
            group_size=7,
        )
        
        assert result.suppressed is True
    
    def test_higher_threshold_more_restrictive(self):
        """Higher threshold should suppress more groups."""
        enforcer_5 = KAnonymityEnforcer(k_threshold=5)
        enforcer_10 = KAnonymityEnforcer(k_threshold=10)
        
        result_5 = enforcer_5.check_and_suppress(data="test", group_size=7)
        result_10 = enforcer_10.check_and_suppress(data="test", group_size=7)
        
        assert result_5.suppressed is False
        assert result_10.suppressed is True


class TestAggregateWithAnonymity:
    """Tests for aggregation with k-anonymity."""
    
    def test_aggregate_avg_with_anonymity(self, enforcer):
        """Average aggregation should respect k-anonymity."""
        records = [
            {"grade": "9", "risk_score": 0.3},
            {"grade": "9", "risk_score": 0.4},
            {"grade": "9", "risk_score": 0.5},
            {"grade": "9", "risk_score": 0.6},
            {"grade": "9", "risk_score": 0.7},  # 5 students in grade 9
            {"grade": "10", "risk_score": 0.2},
            {"grade": "10", "risk_score": 0.3},  # Only 2 students in grade 10
        ]
        
        results = enforcer.aggregate_with_anonymity(
            records=records,
            group_by="grade",
            aggregate_field="risk_score",
            aggregation="avg",
        )
        
        # Grade 9 should pass (5 students)
        assert results["9"].suppressed is False
        assert results["9"].data == pytest.approx(0.5, rel=0.01)
        
        # Grade 10 should be suppressed (2 students)
        assert results["10"].suppressed is True
        assert results["10"].data is None
    
    def test_aggregate_count_with_anonymity(self, enforcer):
        """Count aggregation should respect k-anonymity."""
        records = [
            {"school": "A", "value": 1},
            {"school": "A", "value": 1},
            {"school": "A", "value": 1},
            {"school": "A", "value": 1},
            {"school": "A", "value": 1},
            {"school": "A", "value": 1},  # 6 in school A
            {"school": "B", "value": 1},
            {"school": "B", "value": 1},  # 2 in school B
        ]
        
        results = enforcer.aggregate_with_anonymity(
            records=records,
            group_by="school",
            aggregate_field="value",
            aggregation="count",
        )
        
        assert results["A"].suppressed is False
        assert results["A"].data == 6
        
        assert results["B"].suppressed is True


class TestConvenienceFunction:
    """Tests for the convenience function."""
    
    def test_enforce_k_anonymity_function(self):
        """Convenience function should work correctly."""
        result = enforce_k_anonymity(
            data={"test": "data"},
            group_size=3,
        )
        
        assert result.suppressed is True
    
    def test_enforce_k_anonymity_with_custom_threshold(self):
        """Convenience function should accept custom threshold."""
        result = enforce_k_anonymity(
            data={"test": "data"},
            group_size=3,
            k_threshold=2,
        )
        
        assert result.suppressed is False


class TestEdgeCases:
    """Edge case tests for k-anonymity."""
    
    def test_empty_records_aggregation(self, enforcer):
        """Empty records should return empty results."""
        results = enforcer.aggregate_with_anonymity(
            records=[],
            group_by="grade",
            aggregate_field="risk_score",
            aggregation="avg",
        )
        
        assert len(results) == 0
    
    def test_zero_group_size_suppressed(self, enforcer):
        """Zero group size should be suppressed."""
        result = enforcer.check_and_suppress(
            data={"test": "data"},
            group_size=0,
        )
        
        assert result.suppressed is True
    
    def test_none_data_preserved_when_passing(self, enforcer):
        """None data should be preserved if group passes threshold."""
        result = enforcer.check_and_suppress(
            data=None,
            group_size=10,
        )
        
        assert result.suppressed is False
        assert result.data is None
