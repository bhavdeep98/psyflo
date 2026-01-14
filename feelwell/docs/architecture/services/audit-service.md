# Audit Service

## Purpose

The Audit Service maintains an immutable audit trail per ADR-005. All sensitive actions are logged with cryptographic verification for legal defense and HIPAA/FERPA compliance.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AUDIT SERVICE                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     ALL SERVICES                                 │    │
│  │  Safety │ Observer │ Crisis │ Chat │ Analytics │ Auth           │    │
│  └────────────────────────────┬────────────────────────────────────┘    │
│                               │                                          │
│                               ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     AUDIT LOGGER                                 │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ Entry       │  │ Hash Chain  │  │ Verification│              │    │
│  │  │ Creation    │  │ Linking     │  │ Engine      │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                               │                                          │
│              ┌────────────────┼────────────────┐                        │
│              ▼                ▼                ▼                        │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐             │
│  │ QLDB (Hot)      │  │ PostgreSQL  │  │ S3 Glacier      │             │
│  │ 1 Year          │  │ WORM        │  │ 7+ Years        │             │
│  └─────────────────┘  └─────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

## Audit Actions

### Data Access

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| VIEW_CONVERSATION | Counselor views chat history | student_id_hash, justification |
| VIEW_STUDENT_PROFILE | Access student profile | student_id_hash, justification |
| VIEW_CLINICAL_SCORES | Access PHQ-9/GAD-7 scores | student_id_hash, justification |
| EXPORT_DATA | FERPA data export request | student_id_hash, requester |

### Data Modification

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| CREATE_SESSION | New chat session started | session_id, student_id_hash |
| END_SESSION | Chat session ended | session_id, duration |
| UPDATE_CONSENT | Parental consent changed | student_id_hash, new_status |
| DELETE_DATA | COPPA/GDPR deletion request | student_id_hash, requester |

### Crisis Events

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| CRISIS_DETECTED | Crisis triggered | crisis_id, student_id_hash |
| CRISIS_ACKNOWLEDGED | Counselor acknowledged | crisis_id, acknowledged_by |
| CRISIS_RESOLVED | Crisis resolved | crisis_id, resolution_notes |

## Key Components

### AuditLogger

```python
from feelwell.services.audit_service.audit_logger import (
    AuditLogger, AuditAction, AuditEntity
)

logger = AuditLogger()

# Log data access (FERPA requirement)
logger.log_data_access(
    action=AuditAction.VIEW_CONVERSATION,
    student_id_hash="hash_abc123",
    accessor_id="counselor_001",
    accessor_role="counselor",
    school_id="school_001",
    justification="Student requested meeting"
)

# Log crisis event
logger.log_crisis_event(
    action=AuditAction.CRISIS_DETECTED,
    crisis_id="crisis_xyz",
    student_id_hash="hash_abc123",
    actor_id="system",
    actor_role="system",
    school_id="school_001"
)
```

### Hash Chain Verification

Each audit entry links to the previous entry via SHA-256 hash:

```python
# Verify audit chain integrity
is_valid = logger.verify_chain()
if not is_valid:
    # CRITICAL: Audit trail may have been tampered
    alert_security_team()
```

## AuditEntry Schema

```python
@dataclass(frozen=True)
class AuditEntry:
    entry_id: str           # Unique identifier
    timestamp: datetime     # When action occurred
    action: AuditAction     # What happened
    entity_type: AuditEntity # What was affected
    entity_id: str          # Hashed identifier
    actor_id: str           # Who did it
    actor_role: str         # Their role
    school_id: str          # School context
    details: Dict           # Additional context
    previous_hash: str      # Link to previous entry
    entry_hash: str         # This entry's hash
```

## Storage Tiers (ADR-002)

| Tier | Storage | Retention | Access Time |
|------|---------|-----------|-------------|
| Hot | QLDB | 1 year | < 100ms |
| Warm | PostgreSQL WORM | 7 years | < 1 sec |
| Cold | S3 Glacier | 7+ years | 12 hours |

## Compliance Queries

### FERPA Data Access Report

```python
# Who accessed student data in the last 30 days?
entries = logger.query(
    entity_type=AuditEntity.STUDENT,
    entity_id=student_id_hash,
    start_date=thirty_days_ago
)
```

### SOC 2 Audit Export

```python
# Export all audit entries for compliance review
entries = logger.query(
    start_date=audit_period_start,
    end_date=audit_period_end
)
export_to_csv(entries)
```

## Why Immutable? (ADR-005)

1. **Legal Defense**: Prove what actions were taken and when
2. **Tamper Detection**: Hash chain reveals any modifications
3. **FERPA Compliance**: Track all access to student records
4. **Incident Investigation**: Reconstruct events after a breach
