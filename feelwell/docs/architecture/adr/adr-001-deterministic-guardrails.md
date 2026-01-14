# ADR-001: Deterministic Guardrail Implementation

## Status

Accepted

## Context

Feelwell processes sensitive mental health conversations from minors. A single missed crisis could have catastrophic consequences. LLMs, while powerful, can be unpredictable and may fail to detect crisis language due to:

- Prompt injection attacks
- Model hallucinations
- Coded language not in training data
- Edge cases in natural language understanding

## Decision

Implement a hard-coded regex/NLP filter layer that bypasses the LLM entirely for high-risk inputs.

```
Student Message → Safety Service → [CRISIS?] → Crisis Engine (bypass LLM)
                                 → [SAFE]   → Observer → LLM → Response
```

## Rationale

1. **Deterministic Behavior**: Regex patterns always match the same way
2. **Zero Latency**: No model inference required for crisis detection
3. **Auditability**: Can prove exactly why a crisis was triggered
4. **Fail-Safe**: Works even if LLM service is down

## Consequences

### Positive

- Crisis detection is 100% predictable
- Can be tested exhaustively
- No false negatives for known crisis patterns
- Legal defensibility ("we had a hard-coded rule for this")

### Negative

- Requires constant maintenance of keyword lists
- May miss novel crisis language not in patterns
- Increased system complexity (two detection paths)
- Teen slang evolves faster than pattern updates

## Implementation

```python
# Crisis keywords trigger immediate bypass
CRISIS_KEYWORDS = frozenset({
    "kill myself", "suicide", "want to die",
    "unalive", "become a ghost",  # Teen slang
    "pills", "overdose", "bridge"  # Methods
})

def scan(text: str) -> ScanResult:
    for keyword in CRISIS_KEYWORDS:
        if keyword in text.lower():
            return ScanResult(
                risk_level=RiskLevel.CRISIS,
                bypass_llm=True  # LLM never sees this
            )
```

## Mitigation for Negatives

- Weekly review of missed patterns from Observer Service
- Quarterly "red team" exercises to find bypass attempts
- Integration with BERT model as secondary layer
- Community-sourced teen slang dictionary updates
