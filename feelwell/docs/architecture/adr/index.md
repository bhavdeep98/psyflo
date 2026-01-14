# Architecture Decision Records (ADR) Index

This document indexes all architectural decisions for the Feelwell platform.

## Decision Log

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](./adr-001-deterministic-guardrails.md) | Deterministic Guardrail Implementation | Accepted | 2026-01 |
| [ADR-002](./adr-002-log-tiering.md) | Segregation and Tiering of Logs | Accepted | 2026-01 |
| [ADR-003](./adr-003-zero-pii-logs.md) | Zero PII in Application Logs | Accepted | 2026-01 |
| [ADR-004](./adr-004-event-driven-crisis.md) | Event-Driven Crisis Response Engine | Accepted | 2026-01 |
| [ADR-005](./adr-005-immutable-audit.md) | Immutable Audit Trail | Accepted | 2026-01 |
| [ADR-006](./adr-006-k-anonymity.md) | Mandatory K-Anonymity for Reports | Accepted | 2026-01 |

## Quick Reference

### Safety-Critical Decisions

- **ADR-001**: Crisis keywords bypass LLM entirely
- **ADR-004**: Crisis events are decoupled via Kinesis

### Compliance Decisions

- **ADR-003**: No PII in developer-accessible logs
- **ADR-005**: Immutable audit trail for legal defense
- **ADR-006**: K-anonymity prevents re-identification

### Cost Optimization

- **ADR-002**: Tiered storage reduces costs from $50k/month to $200/month

## Code Generation Rules

When generating code, ensure:

1. **ADR-001**: Safety checks MUST run before LLM calls
2. **ADR-003**: Use `hash_pii()` for all student identifiers in logs
3. **ADR-004**: Crisis events publish to Kinesis, not direct service calls
4. **ADR-005**: All data access operations must emit audit events
5. **ADR-006**: Aggregation queries must check group size before returning
