---
inclusion: always
---

# Feelwell: Architectural Design Decisions (ADR) Tracker

This document tracks critical architectural decisions. All code generation MUST align with these decisions.

## Mission
Provide every student 24/7 access to mental health support, offering school teams visibility into students who need help before small struggles escalate into crises.

## Core Constraints

1. **Compliance (Fort Knox)**: FERPA, COPPA, SOC 2 Type II (HIPAA-ready for clinical referrals)
2. **Safety (Safety-First AI)**: Deterministic guardrails, hard-coded crisis protocol bypasses LLM
3. **Integration (Seamless Adoption)**: SIS integration, SSO-based authentication

---

## Design Decision Log (DDL)

### ADR-001: Deterministic Guardrail Implementation
- **Area**: AI/Safety
- **Decision**: Hard-coded regex/NLP filter layer bypasses LLM for high-risk inputs
- **Rationale**: Safety-First AI Policy - clinical safety and regulatory compliance
- **Trade-offs**: Increased complexity, requires constant filter maintenance

### ADR-002: Segregation and Tiering of Logs
- **Area**: Data Storage
- **Decision**: Parquet/Glacier tiered storage for logs
- **Rationale**: Cost reduction ($50k/month → $200/month), meets 1-7+ year retention requirements
- **Trade-offs**: Glacier retrieval takes up to 12 hours (acceptable for legal subpoenas only)

### ADR-003: Zero PII in Application Logs
- **Area**: Compliance
- **Decision**: No PII in developer-accessible logs
- **Rationale**: SOC 2/FERPA compliance - breach of error logs exposes no PII
- **Trade-offs**: Requires Redaction Middleware, student names replaced with hashed IDs

### ADR-004: Event-Driven Crisis Response Engine
- **Area**: Data Flow
- **Decision**: Kafka/EventBridge for crisis events
- **Rationale**: "Fire Alarm" must be highly available and decoupled - if chat crashes, crisis protocol still executes
- **Trade-offs**: Operational complexity of stream processing

### ADR-005: Immutable Audit Trail
- **Area**: Security/Legal
- **Decision**: QLDB or PostgreSQL with WORM enforcement
- **Rationale**: Unalterable log of sensitive actions for legal defense and HIPAA/FERPA compliance
- **Trade-offs**: QLDB increases AWS vendor lock-in

### ADR-006: Mandatory k-anonymity for Dashboard Reports
- **Area**: Reporting/Privacy
- **Decision**: Suppress data if group size k < 5
- **Rationale**: Prevent reverse-engineering individual student data from aggregated reports
- **Trade-offs**: Limited utility for very small groups/classes

---

## System Architecture

### Service Blocks

| Service | Role | Technologies |
|---------|------|--------------|
| Gateway & Auth Service | Traffic handling, Rate limiting, Anonymization | Mobile App/Web Dashboard, SSO |
| AI & Conversational Engine | Chat logic, Sentiment Scoring, RAG pipeline | LLM, BERT, Vector DB |
| Crisis Response Engine | High-priority safety alerts | Kafka/EventBridge |
| Analytics & Reporting Service | Mood trend aggregation, Dashboard reports | Batch Processes, k-anonymity |

### Logging & Data Flow

All logs flow through Kinesis/Kafka → Redaction Middleware (strips PII) → Tiered Storage:

| Log Stream | Retention | Storage | Purpose |
|------------|-----------|---------|---------|
| Application Logs | 30 Days | OpenSearch/Datadog | Debugging & Performance |
| Interaction Logs | 1-7 Years | MongoDB (Hot) → S3 Parquet (Cold) | Clinical Review & Safety Audits |
| Audit Trail | Permanent (7+ Years) | QLDB/PostgreSQL WORM → S3 Glacier | Legal & Compliance Proof |

---

## Code Generation Rules from ADRs

When generating code, ensure:

1. **ADR-001**: Safety checks MUST run before LLM calls. Crisis keywords trigger immediate bypass.
2. **ADR-003**: Use `hash_pii()` for all student identifiers in logs. Never log raw names/emails.
3. **ADR-004**: Crisis events publish to Kinesis/Kafka, not direct service calls.
4. **ADR-005**: All data access operations must emit audit events.
5. **ADR-006**: Aggregation queries must check group size before returning results.
