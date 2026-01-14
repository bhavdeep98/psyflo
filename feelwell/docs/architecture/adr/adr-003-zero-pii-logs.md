# ADR-003: Zero PII in Application Logs

## Status

Accepted

## Context

Application logs are accessible to developers for debugging and performance monitoring. A breach of these logs could expose student PII, violating FERPA and SOC 2 requirements.

## Decision

No Personally Identifiable Information (PII) in developer-accessible logs. All student identifiers must be hashed before logging.

## Rationale

1. **SOC 2 Compliance**: Breach of error logs exposes no PII
2. **FERPA Compliance**: Student records protected even in logs
3. **Defense in Depth**: Multiple layers of protection
4. **Developer Access**: Devs can debug without accessing PII

## Consequences

### Positive

- Log breach has minimal privacy impact
- Developers can access logs without FERPA training
- Simplified compliance audits
- Reduced liability

### Negative

- Requires Redaction Middleware in log pipeline
- Debugging requires correlation with encrypted interaction logs
- Additional processing overhead

## Implementation

### PII Hashing Utility

```python
from feelwell.shared.utils import hash_pii

# Never log raw student IDs
student_id = "S12345"
student_id_hash = hash_pii(student_id)  # "a1b2c3d4..."

logger.info("Session started", extra={
    "student_id_hash": student_id_hash,  # ✅ Safe
    # "student_id": student_id,          # ❌ Never do this
})
```

### Redaction Middleware

```python
class PIIRedactionMiddleware:
    """Intercepts logs and redacts any PII that slipped through."""
    
    PII_PATTERNS = [
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
        r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',  # Phone
        r'\bS\d{5,}\b',  # Student ID pattern
    ]
    
    def redact(self, log_entry: str) -> str:
        for pattern in self.PII_PATTERNS:
            log_entry = re.sub(pattern, '[REDACTED]', log_entry)
        return log_entry
```

## What IS Logged

- Hashed student IDs (`student_id_hash`)
- Session IDs
- Timestamps
- Risk scores
- Error messages (without PII)
- Performance metrics

## What is NEVER Logged

- Student names
- Email addresses
- Phone numbers
- Raw student IDs
- Message content (in application logs)
- IP addresses
