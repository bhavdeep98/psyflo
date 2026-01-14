"""Audit Service: Immutable audit trail for compliance.

Per ADR-005: QLDB or PostgreSQL with WORM enforcement.
All sensitive actions must be logged with cryptographic verification.

This service provides:
- Immutable logging of all data access operations
- Cryptographic verification of audit entries
- Compliance reporting for SOC 2/FERPA/HIPAA
- Long-term archival to S3 Glacier

Endpoints:
- POST /audit/log - Log generic audit entry
- POST /audit/data-access - Log FERPA data access
- POST /audit/crisis - Log crisis event
- GET /audit/query - Query audit entries
- GET /audit/verify - Verify chain integrity
"""

from .audit_logger import AuditLogger, AuditAction, AuditEntity, AuditEntry

__all__ = [
    "AuditLogger",
    "AuditAction",
    "AuditEntity",
    "AuditEntry",
]
