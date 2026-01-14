"""Tests for k-anonymity enforcement per ADR-006."""
import pytest

from feelwell.shared.utils import configure_pii_salt
from feelwell.services.analytics_service.k_anonymity import (
    KAnonymityEnforcer,
    AggregateResult,
    enforce_k_anonymity,
    K_ANONYMITY_THRESHOLD,
)


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


class TestKAnonymityThreshold:
    """Tests for k-anonymity threshold constant."""
    
    def test_default_threshold_is_5(self):
        assert K_ANONYMITY_THRESHOLD == 5


class TestAggregateResult:
    """Tests for AggregateResult dataclass."""
    
    def test_create_non_suppressed_result(self):
        result = AggregateResult(
            data={"avg": 0.5},
            group_size=10,
            suppressed=False,
        )
        
        assert result.data == {"avg": 0.5}
        assert result.group_size == 10
        assert result.suppressed is False
        assert result.suppression_reason is None
    
    def test_create_suppressed_result(self):
        result = AggregateResult(
            data=None,
            group_size=3,
            suppressed=True,
            suppression_reason="Group too small",
        )
        
        assert result.data is None
        assert result.suppressed is True
        assert "too small" in result.suppression_reason


class TestKAnonymityEnforcer:
    """Tests for KAnonymityEnforcer class."""
    
    def test_default_threshold(self):
        enforcer = KAnonymityEnforcer()
        assert enforcer.k_threshold == 5
    
    def test_custom_threshold(self):
        enforcer = KAnonymityEnforcer(k_threshold=10)
        assert enforcer.k_threshold == 10
    
    def test_suppresses_below_threshold(self):
        enforcer = KAnonymityEnforcer(k_threshold=5)
        
        result = enforcer.check_and_suppress(
            data={"value": 100},
            group_size=4,
        )
        
        assert result.suppressed is True
        assert result.data is None
        assert result.group_size == 4
    
    def test_passes_at_threshold(self):
        enforcer = KAnonymityEnforcer(k_threshold=5)
        
        result = enforcer.check_and_suppress(
            data={"value": 100},
            group_size=5,
        )
        
        assert result.suppressed is False
        assert result.data == {"value": 100}
    
    def test_passes_above_threshold(self):
        enforcer = KAnonymityEnforcer(k_threshold=5)
        
        result = enforcer.check_and_suppress(
            data={"value": 100},
            group_size=10,
        )
        
        assert result.suppressed is False
        assert result.data == {"value": 100}
    
    def test_suppression_reason_includes_sizes(self):
        enforcer = KAnonymityEnforcer(k_threshold=5)
        
        result = enforcer.check_and_suppress(
            data="test",
            group_size=3,
        )
        
        assert "3" in result.suppression_reason
        assert "5" in result.suppression_reason


class TestAggregateWithAnonymity:
    """Tests for aggregate_with_anonymity method."""
    
    def test_aggregates_by_group(self):
        enforcer = KAnonymityEnforcer(k_threshold=2)
        
        records = [
            {"grade": "9th", "score": 0.5},
            {"grade": "9th", "score": 0.7},
            {"grade": "10th", "score": 0.3},
            {"grade": "10th", "score": 0.5},
        ]
        
        results = enforcer.aggregate_with_anonymity(
            records=records,
            group_by="grade",
            aggregate_field="score",
            aggregation="avg",
        )
        
        assert "9th" in results
        assert "10th" in results
        assert results["9th"].suppressed is False
        assert results["10th"].suppressed is False
    
    def test_suppresses_small_groups(self):
        enforcer = KAnonymityEnforcer(k_threshold=5)
        
        records = [
            {"grade": "9th", "score": 0.5},
            {"grade": "9th", "score": 0.7},
            {"grade": "9th", "score": 0.6},  # 3 records - suppressed
        ]
        
        results = enforcer.aggregate_with_anonymity(
            records=records,
            group_by="grade",
            aggregate_field="score",
            aggregation="avg",
        )
        
        assert results["9th"].suppressed is True
    
    def test_count_aggregation(self):
        enforcer = KAnonymityEnforcer(k_threshold=2)
        
        records = [
            {"grade": "9th", "score": 1},
            {"grade": "9th", "score": 1},
            {"grade": "9th", "score": 1},
        ]
        
        results = enforcer.aggregate_with_anonymity(
            records=records,
            group_by="grade",
            aggregate_field="score",
            aggregation="count",
        )
        
        assert results["9th"].data == 3
    
    def test_sum_aggregation(self):
        enforcer = KAnonymityEnforcer(k_threshold=2)
        
        records = [
            {"grade": "9th", "score": 10},
            {"grade": "9th", "score": 20},
            {"grade": "9th", "score": 30},
        ]
        
        results = enforcer.aggregate_with_anonymity(
            records=records,
            group_by="grade",
            aggregate_field="score",
            aggregation="sum",
        )
        
        assert results["9th"].data == 60
    
    def test_handles_missing_values(self):
        enforcer = KAnonymityEnforcer(k_threshold=2)
        
        records = [
            {"grade": "9th", "score": 0.5},
            {"grade": "9th"},  # Missing score
            {"grade": "9th", "score": 0.7},
        ]
        
        results = enforcer.aggregate_with_anonymity(
            records=records,
            group_by="grade",
            aggregate_field="score",
            aggregation="avg",
        )
        
        # Should only count records with score
        assert results["9th"].group_size == 2


class TestEnforceKAnonymityFunction:
    """Tests for convenience function."""
    
    def test_suppresses_below_default_threshold(self):
        result = enforce_k_anonymity(
            data="sensitive",
            group_size=4,
        )
        
        assert result.suppressed is True
    
    def test_passes_above_default_threshold(self):
        result = enforce_k_anonymity(
            data="sensitive",
            group_size=5,
        )
        
        assert result.suppressed is False
    
    def test_custom_threshold(self):
        result = enforce_k_anonymity(
            data="sensitive",
            group_size=8,
            k_threshold=10,
        )
        
        assert result.suppressed is True
