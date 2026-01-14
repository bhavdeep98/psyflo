# Feelwell System Architecture

## Mission

Provide every student 24/7 access to mental health support, offering school teams visibility into students who need help before small struggles escalate into crises.

## Architecture Overview

Feelwell uses a multi-agent orchestration system with safety-first design. The architecture decouples empathetic conversation from clinical monitoring and crisis detection.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           STUDENT INPUT                                  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SAFETY SERVICE                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │ Regex Scanner   │→ │ Pattern Match   │→ │ Risk Decision   │         │
│  │ (Crisis Keywords)│  │ (Coded Language)│  │ SAFE/CAUTION/   │         │
│  └─────────────────┘  └─────────────────┘  │ CRISIS          │         │
│                                             └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
           │                                              │
           │ SAFE/CAUTION                                 │ CRISIS
           ▼                                              ▼
┌─────────────────────────┐                 ┌─────────────────────────────┐
│    OBSERVER SERVICE     │                 │     CRISIS ENGINE           │
│  ┌───────────────────┐  │                 │  ┌───────────────────────┐  │
│  │ Clinical Markers  │  │                 │  │ Event Publisher       │  │
│  │ (PHQ-9, GAD-7)    │  │                 │  │ (Kinesis/EventBridge) │  │
│  └───────────────────┘  │                 │  └───────────────────────┘  │
│  ┌───────────────────┐  │                 │  ┌───────────────────────┐  │
│  │ Session Summary   │  │                 │  │ Escalation Handler    │  │
│  │ (Layer 2)         │  │                 │  │ (State Machine)       │  │
│  └───────────────────┘  │                 │  └───────────────────────┘  │
└─────────────────────────┘                 └─────────────────────────────┘
           │                                              │
           ▼                                              ▼
┌─────────────────────────┐                 ┌─────────────────────────────┐
│    CHAT SERVICE         │                 │   NOTIFICATION SERVICE      │
│    (LLM + RAG)          │                 │   (SMS/Email/In-App)        │
└─────────────────────────┘                 └─────────────────────────────┘
           │                                              │
           └──────────────────┬───────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         AUDIT SERVICE                                    │
│                    (Immutable Audit Trail)                               │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Services

| Service | Purpose | Tech Stack |
|---------|---------|------------|
| Safety Service | Deterministic guardrails, crisis keyword detection | Python, Regex |
| Observer Service | Clinical marker detection (PHQ-9, GAD-7) | Python, BERT |
| Crisis Engine | Event-driven escalation orchestration | Python, Kinesis |
| Audit Service | Immutable audit trail | Python, QLDB |
| Analytics Service | Aggregate reporting with k-anonymity | Python, Redshift |

## Key Design Decisions

See [ADR Index](./adr/index.md) for full decision log.

| ADR | Decision | Rationale |
|-----|----------|-----------|
| ADR-001 | Deterministic guardrails bypass LLM | Safety-first: crisis keywords never reach LLM |
| ADR-003 | Zero PII in application logs | SOC 2/FERPA compliance |
| ADR-004 | Event-driven crisis response | Decoupled "fire alarm" - works even if chat crashes |
| ADR-005 | Immutable audit trail | Legal defense, HIPAA/FERPA compliance |
| ADR-006 | K-anonymity (k≥5) for reports | Prevent re-identification from aggregates |

## Data Flow

### Message Processing Pipeline

1. Student sends message via Chat Service
2. Safety Service scans for crisis keywords (< 50ms)
3. If CRISIS → bypass LLM, trigger Crisis Engine
4. If SAFE/CAUTION → Observer Service analyzes clinical markers
5. Observer publishes risk score to event stream
6. Chat Service generates empathetic response via LLM
7. Audit Service logs all operations

### Three-Layer Risk Assessment

| Layer | Scope | Storage | Purpose |
|-------|-------|---------|---------|
| Layer 1 | Single message | MongoDB | Real-time risk snapshot |
| Layer 2 | Session | PostgreSQL | Aggregated session summary |
| Layer 3 | Longitudinal | Redshift | Multi-week trend analysis |

## Compliance Framework

| Regulation | Status | Key Controls |
|------------|--------|--------------|
| FERPA | ✅ Compliant | RBAC, audit logging, data export APIs |
| COPPA | ✅ Compliant | Parental consent workflow, age verification |
| SOC 2 Type II | 🔄 In Progress | Encryption, WAF, audit trail |
| HIPAA | 🔮 Future-Ready | BAA with AWS, PHI encryption |

## Repository Structure

```
feelwell/
├── services/
│   ├── safety_service/      # Crisis detection, keyword scanning
│   ├── observer_service/    # Clinical marker analysis
│   ├── crisis_engine/       # Escalation orchestration
│   ├── audit_service/       # Immutable audit trail
│   └── analytics_service/   # K-anonymity reporting
├── shared/
│   ├── models/              # Domain models (RiskLevel, ClinicalMarker)
│   └── utils/               # PII hashing, common utilities
└── docs/
    └── architecture/        # This documentation
```
