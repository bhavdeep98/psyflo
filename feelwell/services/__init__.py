"""Feelwell microservices.

Service architecture follows the ADR decisions:
- ADR-001: Safety Service runs before LLM (deterministic guardrails)
- ADR-003: All services use hash_pii() for student identifiers
- ADR-004: Crisis Engine uses event-driven architecture
- ADR-005: Audit Service provides immutable audit trail
- ADR-006: Analytics Service enforces k-anonymity
"""
