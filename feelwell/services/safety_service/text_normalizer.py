"""Text normalization for safety scanning - handles evasion techniques.

This module normalizes text to catch adversarial attempts to bypass
crisis detection using leetspeak, unicode substitution, character
separation, and other obfuscation techniques.

Per ADR-001: Deterministic guardrails must catch crisis language
even when disguised. This is safety-critical code.
"""
import logging
import re
import unicodedata
from typing import Dict, FrozenSet

logger = logging.getLogger(__name__)


# Leetspeak character mappings (numbers/symbols → letters)
LEETSPEAK_MAP: Dict[str, str] = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "6": "g",
    "7": "t",
    "8": "b",
    "9": "g",
    "@": "a",
    "$": "s",
    "!": "i",
    "+": "t",
    "(": "c",
    "|": "l",
}

# Unicode mathematical/styled letter ranges to normalize
# These map fancy unicode letters back to ASCII
UNICODE_LETTER_RANGES: Dict[str, tuple] = {
    # Mathematical Bold (𝐀-𝐙, 𝐚-𝐳)
    "math_bold_upper": (0x1D400, 0x1D419, ord("A")),
    "math_bold_lower": (0x1D41A, 0x1D433, ord("a")),
    # Mathematical Italic
    "math_italic_upper": (0x1D434, 0x1D44D, ord("A")),
    "math_italic_lower": (0x1D44E, 0x1D467, ord("a")),
    # Mathematical Double-Struck (𝔸-𝕫)
    "math_double_upper": (0x1D538, 0x1D551, ord("A")),
    "math_double_lower": (0x1D552, 0x1D56B, ord("a")),
    # Circled letters (Ⓐ-Ⓩ, ⓐ-ⓩ)
    "circled_upper": (0x24B6, 0x24CF, ord("A")),
    "circled_lower": (0x24D0, 0x24E9, ord("a")),
    # Fullwidth letters (Ａ-Ｚ, ａ-ｚ)
    "fullwidth_upper": (0xFF21, 0xFF3A, ord("A")),
    "fullwidth_lower": (0xFF41, 0xFF5A, ord("a")),
}

# Characters to strip (zero-width, invisible, separators)
STRIP_CHARS: FrozenSet[str] = frozenset({
    "\u200b",  # Zero-width space
    "\u200c",  # Zero-width non-joiner
    "\u200d",  # Zero-width joiner
    "\ufeff",  # Byte order mark
    "\u00ad",  # Soft hyphen
    "\u2060",  # Word joiner
})


class TextNormalizer:
    """Normalizes text to defeat evasion techniques.
    
    Handles:
    - Leetspeak (K1LL → KILL)
    - Unicode substitution (ⓚⓘⓛⓛ → kill)
    - Dot/character separation (k.i.l.l → kill)
    - Newline separation (k\\ni\\nl\\nl → kill)
    - Zero-width characters
    - Mixed case (already handled by scanner, but normalized here too)
    
    This is safety-critical code per ADR-001.
    """
    
    def __init__(self):
        """Initialize the normalizer with precompiled patterns."""
        # Pattern to detect separator characters between single letters
        # Matches: single letter + separator(s) + single letter
        # But only when both letters are isolated (not part of a word)
        self._separator_pattern = re.compile(r"\b([a-zA-Z])[\.\-_]+([a-zA-Z])\b")
        
        # Pattern for space-separated single letters (k i l l)
        self._space_letter_pattern = re.compile(r"\b([a-zA-Z])\s+([a-zA-Z])\b")
        
        # Pattern for newline-separated letters
        self._newline_pattern = re.compile(r"\b([a-zA-Z])[\n\r]+([a-zA-Z])\b")
        
        logger.info(
            "TEXT_NORMALIZER_INITIALIZED",
            extra={
                "leetspeak_mappings": len(LEETSPEAK_MAP),
                "unicode_ranges": len(UNICODE_LETTER_RANGES),
            }
        )
    
    def normalize(self, text: str) -> str:
        """Normalize text to catch evasion attempts.
        
        Applies normalization in order:
        1. Strip zero-width/invisible characters
        2. Normalize unicode to ASCII equivalents
        3. Apply leetspeak conversion
        4. Remove separator characters between letters
        5. Collapse whitespace
        6. Lowercase
        
        Args:
            text: Raw input text
            
        Returns:
            Normalized text for pattern matching
        """
        if not text:
            return ""
        
        result = text
        
        # Step 1: Strip invisible characters
        result = self._strip_invisible(result)
        
        # Step 2: Normalize unicode letters to ASCII
        result = self._normalize_unicode(result)
        
        # Step 3: Apply leetspeak conversion
        result = self._convert_leetspeak(result)
        
        # Step 4: Remove separators between letters (k.i.l.l → kill)
        result = self._remove_letter_separators(result)
        
        # Step 5: Collapse whitespace
        result = " ".join(result.split())
        
        # Step 6: Lowercase
        result = result.lower()
        
        return result
    
    def _strip_invisible(self, text: str) -> str:
        """Remove zero-width and invisible characters.
        
        Args:
            text: Input text
            
        Returns:
            Text with invisible characters removed
        """
        return "".join(c for c in text if c not in STRIP_CHARS)
    
    def _normalize_unicode(self, text: str) -> str:
        """Convert unicode styled letters to ASCII equivalents.
        
        Handles mathematical letters, circled letters, fullwidth, etc.
        
        Args:
            text: Input text
            
        Returns:
            Text with unicode letters normalized to ASCII
        """
        result = []
        for char in text:
            code_point = ord(char)
            normalized = False
            
            # Check each unicode range
            for range_name, (start, end, base) in UNICODE_LETTER_RANGES.items():
                if start <= code_point <= end:
                    # Map to ASCII equivalent
                    ascii_char = chr(base + (code_point - start))
                    result.append(ascii_char)
                    normalized = True
                    break
            
            if not normalized:
                # Try NFKD normalization for other unicode
                normalized_char = unicodedata.normalize("NFKD", char)
                # Keep only ASCII characters from decomposition
                ascii_only = "".join(
                    c for c in normalized_char 
                    if unicodedata.category(c) != "Mn" and ord(c) < 128
                )
                result.append(ascii_only if ascii_only else char)
        
        return "".join(result)
    
    def _convert_leetspeak(self, text: str) -> str:
        """Convert leetspeak characters to letters.
        
        Args:
            text: Input text
            
        Returns:
            Text with leetspeak converted to letters
        """
        result = []
        for char in text:
            if char in LEETSPEAK_MAP:
                result.append(LEETSPEAK_MAP[char])
            else:
                result.append(char)
        return "".join(result)
    
    def _remove_letter_separators(self, text: str) -> str:
        """Remove separator characters between single letters.
        
        Converts patterns like k.i.l.l or k-i-l-l to kill.
        Only affects single letters separated by punctuation, not normal words.
        
        Args:
            text: Input text
            
        Returns:
            Text with letter separators removed
        """
        # Apply all separator patterns repeatedly until no more matches
        # This handles chains like k.i.l.l → ki.ll → kill
        max_iterations = 20  # Safety limit to prevent infinite loops
        
        for _ in range(max_iterations):
            original = text
            
            # Remove dot/dash/underscore separators
            text = self._separator_pattern.sub(r"\1\2", text)
            
            # Remove newline separators
            text = self._newline_pattern.sub(r"\1\2", text)
            
            # Remove space separators between single letters
            text = self._space_letter_pattern.sub(r"\1\2", text)
            
            # If nothing changed, we're done
            if text == original:
                break
        
        return text


# Module-level singleton for performance
_normalizer: TextNormalizer | None = None


def get_normalizer() -> TextNormalizer:
    """Get the singleton TextNormalizer instance.
    
    Returns:
        TextNormalizer instance
    """
    global _normalizer
    if _normalizer is None:
        _normalizer = TextNormalizer()
    return _normalizer


def normalize_text(text: str) -> str:
    """Convenience function to normalize text.
    
    Args:
        text: Raw input text
        
    Returns:
        Normalized text for pattern matching
    """
    return get_normalizer().normalize(text)
