"""PII handling utilities following ADR-003: Zero PII in Application Logs.

All student identifiers must be hashed before logging or storage in
developer-accessible systems.
"""
import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Salt should be loaded from AWS Secrets Manager in production
# Using placeholder for development
_PII_SALT: Optional[str] = None


def configure_pii_salt(salt: str) -> None:
    """Configure the PII hashing salt from secrets manager.
    
    Must be called during application startup before any PII hashing.
    
    Args:
        salt: Secret salt value from AWS Secrets Manager
        
    Raises:
        ValueError: If salt is empty or too short
    """
    global _PII_SALT
    if not salt or len(salt) < 32:
        logger.critical(
            "PII_SALT_CONFIGURATION_FAILED",
            extra={"reason": "Salt too short or empty", "min_length": 32}
        )
        raise ValueError("PII salt must be at least 32 characters")
    
    _PII_SALT = salt
    logger.info("PII_SALT_CONFIGURED", extra={"salt_length": len(salt)})


def hash_pii(value: str) -> str:
    """Hash a PII value for safe logging and storage.
    
    Uses SHA-256 with a secret salt to create a consistent, 
    non-reversible hash of student identifiers.
    
    Args:
        value: The PII value to hash (student ID, email, etc.)
        
    Returns:
        Hashed string safe for logging
        
    Raises:
        RuntimeError: If PII salt has not been configured
        
    Example:
        >>> hash_pii("student@school.edu")
        'a1b2c3d4e5f6...'  # 64-char hex string
    """
    if _PII_SALT is None:
        logger.critical(
            "PII_HASH_FAILED",
            extra={"reason": "Salt not configured", "action": "call configure_pii_salt()"}
        )
        raise RuntimeError("PII salt not configured. Call configure_pii_salt() first.")
    
    salted = f"{_PII_SALT}{value}"
    return hashlib.sha256(salted.encode()).hexdigest()


def hash_text_for_audit(text: str) -> str:
    """Hash message text for audit trail without exposing content.
    
    Used to create a fingerprint of message content that can be
    matched against the encrypted original if needed for legal review.
    
    Args:
        text: Raw message text
        
    Returns:
        SHA-256 hash of the text
    """
    return hashlib.sha256(text.encode()).hexdigest()
