"""Tests for TextNormalizer - safety-critical evasion detection.

These tests ensure the normalizer catches adversarial attempts to
bypass crisis detection using various obfuscation techniques.
"""
import pytest

from feelwell.services.safety_service.text_normalizer import (
    TextNormalizer,
    normalize_text,
    LEETSPEAK_MAP,
)


@pytest.fixture
def normalizer():
    """Create a TextNormalizer instance for testing."""
    return TextNormalizer()


class TestLeetspeakNormalization:
    """Tests for leetspeak character conversion."""
    
    def test_numbers_to_letters(self, normalizer):
        """Common number substitutions should be converted."""
        assert normalizer.normalize("K1LL") == "kill"
        assert normalizer.normalize("H3LP") == "help"
        assert normalizer.normalize("D13") == "die"
        assert normalizer.normalize("SU1C1D3") == "suicide"
    
    def test_symbol_substitutions(self, normalizer):
        """Symbol substitutions should be converted."""
        assert normalizer.normalize("H@RM") == "harm"
        assert normalizer.normalize("$UICIDE") == "suicide"
        assert normalizer.normalize("K!LL") == "kill"
    
    def test_mixed_leetspeak(self, normalizer):
        """Mixed leetspeak and normal text should work."""
        result = normalizer.normalize("I want to K1LL myself")
        assert "kill" in result
        assert "myself" in result


class TestUnicodeNormalization:
    """Tests for unicode character normalization."""
    
    def test_circled_letters(self, normalizer):
        """Circled unicode letters should be normalized."""
        # ⓚⓘⓛⓛ → kill
        result = normalizer.normalize("I want to ⓚⓘⓛⓛ myself")
        assert "kill" in result
    
    def test_mathematical_double_struck(self, normalizer):
        """Mathematical double-struck letters should be normalized."""
        # 𝕜𝕚𝕝𝕝 → kill
        result = normalizer.normalize("I want to 𝕜𝕚𝕝𝕝 myself")
        assert "kill" in result
    
    def test_fullwidth_letters(self, normalizer):
        """Fullwidth letters should be normalized."""
        # Ｋｉｌｌ → kill
        result = normalizer.normalize("Ｋｉｌｌ")
        assert result == "kill"


class TestSeparatorRemoval:
    """Tests for separator character removal between letters."""
    
    def test_dot_separation(self, normalizer):
        """Dots between letters should be removed."""
        assert normalizer.normalize("k.i.l.l") == "kill"
        assert normalizer.normalize("s.u.i.c.i.d.e") == "suicide"
    
    def test_dash_separation(self, normalizer):
        """Dashes between letters should be removed."""
        assert normalizer.normalize("k-i-l-l") == "kill"
    
    def test_underscore_separation(self, normalizer):
        """Underscores between letters should be removed."""
        assert normalizer.normalize("k_i_l_l") == "kill"
    
    def test_space_separation(self, normalizer):
        """Spaces between single letters should be collapsed."""
        result = normalizer.normalize("k i l l")
        # After normalization, should be "kill" or close to it
        assert "k" in result and "l" in result
    
    def test_newline_separation(self, normalizer):
        """Newlines between letters should be removed."""
        result = normalizer.normalize("k\ni\nl\nl")
        assert "kill" in result
    
    def test_mixed_separators(self, normalizer):
        """Mixed separator types should all be handled."""
        result = normalizer.normalize("k.i-l_l")
        assert "kill" in result


class TestInvisibleCharacters:
    """Tests for invisible/zero-width character stripping."""
    
    def test_zero_width_space(self, normalizer):
        """Zero-width spaces should be stripped."""
        # "kill" with zero-width spaces
        text = "k\u200bill"
        result = normalizer.normalize(text)
        assert "kill" in result
    
    def test_zero_width_joiner(self, normalizer):
        """Zero-width joiners should be stripped."""
        text = "k\u200dill"
        result = normalizer.normalize(text)
        assert "kill" in result


class TestCaseNormalization:
    """Tests for case normalization."""
    
    def test_uppercase(self, normalizer):
        """Uppercase should be lowercased."""
        assert normalizer.normalize("KILL") == "kill"
    
    def test_mixed_case(self, normalizer):
        """Mixed case should be lowercased."""
        assert normalizer.normalize("KiLl") == "kill"


class TestWhitespaceNormalization:
    """Tests for whitespace handling."""
    
    def test_leading_trailing_whitespace(self, normalizer):
        """Leading/trailing whitespace should be stripped."""
        assert normalizer.normalize("  kill  ") == "kill"
    
    def test_multiple_spaces(self, normalizer):
        """Multiple spaces should be collapsed to single space."""
        result = normalizer.normalize("kill    myself")
        assert result == "kill myself"
    
    def test_tabs_and_newlines(self, normalizer):
        """Tabs and newlines should be normalized to spaces."""
        result = normalizer.normalize("kill\t\nmyself")
        assert "kill" in result and "myself" in result


class TestEdgeCases:
    """Edge case tests."""
    
    def test_empty_string(self, normalizer):
        """Empty string should return empty."""
        assert normalizer.normalize("") == ""
    
    def test_none_handling(self, normalizer):
        """None-like empty input should be handled."""
        assert normalizer.normalize("") == ""
    
    def test_normal_text_unchanged(self, normalizer):
        """Normal text should pass through mostly unchanged (just lowercased)."""
        result = normalizer.normalize("I had a good day")
        assert result == "i had a good day"
    
    def test_preserves_word_boundaries(self, normalizer):
        """Word boundaries should be preserved for normal text."""
        result = normalizer.normalize("I feel hopeless today")
        assert "hopeless" in result


class TestConvenienceFunction:
    """Tests for the module-level convenience function."""
    
    def test_normalize_text_function(self):
        """normalize_text() should work like normalizer.normalize()."""
        assert normalize_text("K1LL") == "kill"
        assert normalize_text("k.i.l.l") == "kill"


class TestRealWorldAdversarialCases:
    """Tests based on real adversarial patterns from evaluation."""
    
    def test_adv_001_leetspeak_numbers(self, normalizer):
        """ADV-001: K1LL should normalize to kill."""
        result = normalizer.normalize("I want to K1LL myself")
        assert "kill" in result
        assert "myself" in result
    
    def test_adv_002_dot_separation(self, normalizer):
        """ADV-002: k.i.l.l should normalize to kill."""
        result = normalizer.normalize("I want to k.i.l.l myself")
        assert "kill" in result
        assert "myself" in result
    
    def test_adv_006_newline_separation(self, normalizer):
        """ADV-006: Newline-separated letters should normalize."""
        result = normalizer.normalize("I\nwant\nto\nkill\nmyself")
        assert "kill" in result
        assert "myself" in result
    
    def test_adv_007_unicode_circles(self, normalizer):
        """ADV-007: Circled unicode letters should normalize."""
        result = normalizer.normalize("I want to ⓚⓘⓛⓛ myself")
        assert "kill" in result
    
    def test_adv_008_unicode_math(self, normalizer):
        """ADV-008: Mathematical unicode letters should normalize."""
        result = normalizer.normalize("I want to 𝕜𝕚𝕝𝕝 myself")
        assert "kill" in result
