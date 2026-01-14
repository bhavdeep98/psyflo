# Safety Service

## Purpose

The Safety Service is the first line of defense in the Feelwell system. Every student message passes through this service BEFORE reaching the LLM. It implements deterministic guardrails per ADR-001.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     SAFETY SERVICE                           │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Input      │ →  │   Scanner    │ →  │   Decision   │  │
│  │   Message    │    │   Pipeline   │    │   Engine     │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│                             │                    │          │
│                      ┌──────┴──────┐      ┌──────┴──────┐  │
│                      │ Regex Layer │      │ SAFE        │  │
│                      │ BERT Layer  │      │ CAUTION     │  │
│                      │ Pattern     │      │ CRISIS      │  │
│                      └─────────────┘      └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### SafetyScanner

Main entry point for message scanning.

```python
from feelwell.services.safety_service.scanner import SafetyScanner

scanner = SafetyScanner()
result = scanner.scan(
    message_id="msg_123",
    text="I'm feeling stressed about exams",
    student_id="student_456"
)

if result.bypass_llm:
    # CRISIS detected - route to Crisis Engine
    trigger_crisis_protocol(result)
else:
    # SAFE or CAUTION - continue to Observer Service
    continue_to_observer(result)
```

### ScanResult

Immutable result of safety scan.

| Field | Type | Description |
|-------|------|-------------|
| message_id | str | Unique message identifier |
| risk_level | RiskLevel | SAFE, CAUTION, or CRISIS |
| risk_score | float | 0.0 to 1.0 |
| bypass_llm | bool | True if LLM should be bypassed |
| matched_keywords | List[str] | Keywords that triggered detection |
| scan_latency_ms | float | Processing time |

## Crisis Keywords

The scanner maintains two keyword sets:

### Crisis Keywords (Immediate Bypass)

These trigger immediate LLM bypass and Crisis Engine activation:

- Direct self-harm language: "kill myself", "suicide", "want to die"
- Methods: "pills", "overdose", "bridge", "rope", "cutting"
- Coded language: "unalive", "become a ghost", "goodbye forever"
- Psychosis indicators: "voices telling me"

### Caution Keywords (Elevated Risk)

These elevate risk score but allow LLM response:

- "hopeless", "worthless", "burden"
- "nobody cares", "alone", "can't go on"
- "hate myself", "failure", "trapped"

## Performance Requirements

| Metric | Target | Rationale |
|--------|--------|-----------|
| Latency (p99) | < 50ms | Must not block chat flow |
| False Negative Rate | 0% | Cannot miss a crisis |
| False Positive Rate | < 5% | Minimize unnecessary escalations |

## Logging

All scans are logged per ADR-003 (no PII in logs):

```python
logger.info("SAFETY_SCAN_COMPLETED", extra={
    "message_id": "msg_123",
    "student_id_hash": "a1b2c3...",  # Hashed, not raw
    "risk_level": "CAUTION",
    "risk_score": 0.45,
    "latency_ms": 12.3
})
```

## Testing

Safety-critical code requires 100% test coverage. See `tests/test_scanner.py` for:

- Normal message handling
- Crisis keyword detection
- Adversarial cases (case variations, coded language)
- Word boundary validation (prevent false positives)
