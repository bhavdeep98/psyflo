# ADR-005: Immutable Audit Trail

## Status

Accepted

## Context

Feelwell handles sensitive student mental health data. In case of legal action (e.g., "why wasn't my child's crisis detected?"), we need an unalterable record of all system actions.

## Decision

Use QLDB or PostgreSQL with WORM (Write Once Read Many) enforcement for the audit trail. All entries are cryptographically linked via hash chain.

## Rationale

1. **Legal Defense**: Prove what actions were taken and when
2. **Tamper Detection**: Hash chain reveals any modifications
3. **FERPA Compliance**: Track all access to student records
4. **HIPAA Readiness**: Required for clinical referral integration

## Consequences

### Positive

- Cryptographically verifiable audit trail
- Cannot be altered after the fact
- Supports legal discovery requests
- Meets compliance requirements

### Negative

- QLDB increases AWS vendor lock-in
- Higher storage costs than regular database
- Cannot delete entries (by design)
- Requires careful schema design upfront

## Implementation

### Hash Chain

Each audit entry links to the previous entry:

```python
@dataclass(frozen=True)
class AuditEntry:
    entry_id: str
    timestamp: datetime
    action: AuditAction
    entity_id: str
    actor_id: str
    details: Dict
    previous_hash: str  # Link to previous entry
    entry_hash: str     # This entry's hash

    def compute_hash(self) -> str:
        content = json.dumps({
            "entry_id": self.entry_id,
            "timestamp": self.timestamp.isoformat(),
            "action": self.action.value,
            # ... all fields except entry_hash
            "previous_hash": self.previous_hash
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
```

### Chain Verification

```python
def verify_chain(entries: List[AuditEntry]) -> bool:
    """Verify no entries have been tampered with."""
    expected_prev = "genesis"
    for entry in entries:
        if entry.previous_hash != expected_prev:
            return False  # Chain broken
        if entry.compute_hash() != entry.entry_hash:
            return False  # Entry tampered
        expected_prev = entry.entry_hash
    return True
```

### QLDB Configuration

```hcl
resource "aws_qldb_ledger" "audit_trail" {
  name                = "feelwell-audit-trail"
  permissions_mode    = "STANDARD"
  deletion_protection = true

  tags = {
    Environment = "production"
    Compliance  = "FERPA,HIPAA"
  }
}
```

## What Gets Audited

| Action | Required Fields |
|--------|-----------------|
| VIEW_CONVERSATION | student_id_hash, accessor, justification |
| VIEW_CLINICAL_SCORES | student_id_hash, accessor, justification |
| CRISIS_DETECTED | crisis_id, student_id_hash, trigger |
| CRISIS_RESOLVED | crisis_id, resolver, resolution_notes |
| DATA_EXPORT | student_id_hash, requester, purpose |
| DATA_DELETE | student_id_hash, requester, legal_basis |

## Retention

| Tier | Storage | Retention |
|------|---------|-----------|
| Hot | QLDB | 1 year |
| Warm | PostgreSQL WORM | 7 years |
| Cold | S3 Glacier Deep Archive | Permanent |
