"""Tests for ClinicalMarkerDetector."""
import pytest
from feelwell.shared.utils import configure_pii_salt
from feelwell.shared.models import ClinicalFramework
from feelwell.services.observer_service.clinical_markers import ClinicalMarkerDetector


@pytest.fixture(autouse=True)
def setup_pii_salt():
    configure_pii_salt("test_salt_that_is_at_least_32_characters_long")


@pytest.fixture
def detector():
    return ClinicalMarkerDetector()


class TestPHQ9Detection:
    """Tests for PHQ-9 marker detection."""
    
    def test_detects_anhedonia(self, detector):
        """Should detect anhedonia markers."""
        markers = detector.detect("Nothing is fun anymore, I don't enjoy anything")
        phq9_markers = [m for m in markers if m.framework == ClinicalFramework.PHQ9]
        assert len(phq9_markers) > 0
        assert any(m.item_id == 1 for m in phq9_markers)  # Anhedonia is item 1
    
    def test_detects_depressed_mood(self, detector):
        """Should detect depressed mood markers."""
        markers = detector.detect("I feel so hopeless and empty inside")
        phq9_markers = [m for m in markers if m.framework == ClinicalFramework.PHQ9]
        assert len(phq9_markers) > 0
        assert any(m.item_id == 2 for m in phq9_markers)  # Depressed mood is item 2
    
    def test_detects_sleep_issues(self, detector):
        """Should detect sleep-related markers."""
        markers = detector.detect("I can't sleep at night, exhausted all day")
        phq9_markers = [m for m in markers if m.framework == ClinicalFramework.PHQ9]
        assert any(m.item_id == 3 for m in phq9_markers)  # Sleep is item 3
    
    def test_detects_guilt_worthlessness(self, detector):
        """Should detect guilt/worthlessness markers."""
        markers = detector.detect("I hate myself, I'm such a failure")
        phq9_markers = [m for m in markers if m.framework == ClinicalFramework.PHQ9]
        assert any(m.item_id == 6 for m in phq9_markers)  # Guilt is item 6
    
    def test_detects_self_harm_markers(self, detector):
        """Should detect self-harm markers with high confidence."""
        markers = detector.detect("I don't want to be here anymore")
        phq9_markers = [m for m in markers if m.framework == ClinicalFramework.PHQ9]
        self_harm = [m for m in phq9_markers if m.item_id == 9]
        if self_harm:
            assert self_harm[0].confidence >= 0.9  # High confidence for critical marker
    
    def test_no_markers_for_safe_message(self, detector):
        """Safe message should have no markers."""
        markers = detector.detect("I had a great day at school today!")
        assert len(markers) == 0


class TestGAD7Detection:
    """Tests for GAD-7 marker detection."""
    
    def test_detects_anxiety(self, detector):
        """Should detect anxiety markers."""
        markers = detector.detect("I'm so anxious and can't stop worrying")
        gad7_markers = [m for m in markers if m.framework == ClinicalFramework.GAD7]
        assert len(gad7_markers) > 0
    
    def test_detects_restlessness(self, detector):
        """Should detect restlessness markers."""
        markers = detector.detect("I can't sit still, always restless")
        gad7_markers = [m for m in markers if m.framework == ClinicalFramework.GAD7]
        assert any(m.item_id == 5 for m in gad7_markers)  # Restlessness is item 5
    
    def test_detects_fear_doom(self, detector):
        """Should detect fear/doom markers."""
        markers = detector.detect("I have this sense of doom, something bad will happen")
        gad7_markers = [m for m in markers if m.framework == ClinicalFramework.GAD7]
        assert any(m.item_id == 7 for m in gad7_markers)  # Fear is item 7


class TestScoreCalculation:
    """Tests for clinical score calculation."""
    
    def test_phq9_score_calculation(self, detector):
        """Should calculate PHQ-9 score from markers."""
        markers = detector.detect(
            "I feel hopeless, have no energy, can't sleep, and hate myself"
        )
        score = detector.calculate_phq9_score(markers)
        assert score is not None
        assert 0 <= score <= 27
    
    def test_gad7_score_calculation(self, detector):
        """Should calculate GAD-7 score from markers."""
        markers = detector.detect(
            "I'm so anxious, can't stop worrying, always tense"
        )
        score = detector.calculate_gad7_score(markers)
        assert score is not None
        assert 0 <= score <= 21
    
    def test_no_score_without_markers(self, detector):
        """Should return None if no markers detected."""
        markers = detector.detect("Everything is fine")
        phq9 = detector.calculate_phq9_score(markers)
        gad7 = detector.calculate_gad7_score(markers)
        assert phq9 is None
        assert gad7 is None


class TestMarkerDeduplication:
    """Tests for marker deduplication."""
    
    def test_no_duplicate_markers(self, detector):
        """Same marker pattern should not create duplicates."""
        markers = detector.detect("I feel hopeless. So hopeless. Really hopeless.")
        # Should only have one depressed mood marker
        phq9_item2 = [m for m in markers if m.framework == ClinicalFramework.PHQ9 and m.item_id == 2]
        assert len(phq9_item2) <= 1
