# ADR-004: Event-Driven Crisis Response Engine

## Status

Accepted

## Context

The Crisis Response Engine is the "fire alarm" of the system. If a student expresses suicidal ideation, the system must alert a counselor immediately. This must work even if other services are experiencing issues.

## Decision

Use Kinesis/EventBridge for crisis events instead of direct service calls. The Crisis Engine is decoupled from the Chat Service.

```
Safety Service → Kinesis → Crisis Engine → Notification Service
                   ↑
Observer Service ──┘
```

## Rationale

1. **High Availability**: Crisis alerts work even if Chat Service crashes
2. **Guaranteed Delivery**: Kinesis provides at-least-once delivery
3. **Decoupling**: Services can fail independently
4. **Audit Trail**: All events are persisted for compliance

## Consequences

### Positive

- Crisis detection is resilient to service failures
- Events are durably stored (can replay if needed)
- Scalable to handle burst of crisis events
- Clear audit trail of all crisis events

### Negative

- Operational complexity of stream processing
- Eventual consistency (small delay in event processing)
- Additional infrastructure to maintain
- Learning curve for event-driven patterns

## Implementation

### Event Publishing

```python
from feelwell.services.crisis_engine.events import CrisisEventPublisher

publisher = CrisisEventPublisher(stream_name="feelwell-crisis-events")

event = publisher.create_crisis_event(
    student_id_hash="hash_abc123",
    session_id="sess_xyz",
    trigger_source="safety_service",
    trigger_keywords=["kill myself"]
)

# Publishes to Kinesis - guaranteed delivery
publisher.publish(event)
```

### Event Schema

```json
{
  "event_id": "evt_abc123",
  "event_type": "safety.crisis.detected",
  "timestamp": "2026-01-14T10:30:00Z",
  "source": "safety-service",
  "data": {
    "student_id_hash": "a3c4f9...",
    "session_id": "sess_xyz789",
    "risk_level": "CRISIS",
    "requires_human_intervention": true
  }
}
```

### Kinesis Configuration

```hcl
resource "aws_kinesis_stream" "crisis_events" {
  name             = "feelwell-crisis-events"
  shard_count      = 2
  retention_period = 168  # 7 days

  # Enable encryption
  encryption_type = "KMS"
  kms_key_id      = aws_kms_key.crisis_events.id
}
```

## Failure Scenarios

| Scenario | Behavior |
|----------|----------|
| Chat Service down | Crisis events still published to Kinesis |
| Crisis Engine down | Events queue in Kinesis, processed on recovery |
| Kinesis down | Fallback to direct SNS notification |
| Notification Service down | Events retry with exponential backoff |
