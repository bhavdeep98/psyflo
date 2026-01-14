# Crisis Engine

## Purpose

The Crisis Engine is the "fire alarm" of the Feelwell system. Per ADR-004, it uses event-driven architecture to ensure crisis response works even if other services fail.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CRISIS ENGINE                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     EVENT SOURCES                                │    │
│  │  ┌─────────────────┐         ┌─────────────────┐                │    │
│  │  │ Safety Service  │         │ Observer Service│                │    │
│  │  │ (CRISIS bypass) │         │ (Threshold)     │                │    │
│  │  └────────┬────────┘         └────────┬────────┘                │    │
│  └───────────┼───────────────────────────┼─────────────────────────┘    │
│              │                           │                               │
│              ▼                           ▼                               │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    KINESIS / EVENTBRIDGE                         │    │
│  │              (Decoupled Event Stream - ADR-004)                  │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                  │                                       │
│                                  ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     CRISIS HANDLER                               │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐              │    │
│  │  │ State       │  │ Escalation  │  │ Notification│              │    │
│  │  │ Machine     │  │ Router      │  │ Trigger     │              │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘              │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                  │                                       │
│                                  ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     DYNAMODB (Crisis Records)                    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘
```

## Event Types

| Event Type | Source | Trigger |
|------------|--------|---------|
| `safety.crisis.detected` | Safety Service | Crisis keyword matched |
| `observer.threshold.exceeded` | Observer Service | Risk score > 0.7 |
| `crisis.acknowledged` | Counselor Dashboard | Counselor saw alert |
| `crisis.resolved` | Counselor Dashboard | Crisis addressed |

## Crisis State Machine

```
DETECTED → NOTIFYING → ACKNOWLEDGED → IN_PROGRESS → RESOLVED
                │                           │
                └──────── ESCALATED ────────┘
                   (if not acknowledged)
```

## Key Components

### CrisisEventPublisher

Publishes events to Kinesis stream.

```python
from feelwell.services.crisis_engine.events import CrisisEventPublisher

publisher = CrisisEventPublisher(stream_name="feelwell-crisis-events")
event = publisher.create_crisis_event(
    student_id_hash="hash_abc123",
    session_id="sess_xyz",
    trigger_source="safety_service",
    trigger_keywords=["kill myself"],
    school_id="school_001"
)
publisher.publish(event)
```

### CrisisHandler

Orchestrates crisis response.

```python
from feelwell.services.crisis_engine.handler import CrisisHandler

handler = CrisisHandler()

# Handle crisis from Safety Service
record = handler.handle_safety_crisis(
    student_id_hash="hash_abc123",
    session_id="sess_xyz",
    matched_keywords=["kill myself"],
    school_id="school_001"
)

# Counselor acknowledges
handler.acknowledge(
    crisis_id=record.crisis_id,
    acknowledged_by="counselor_001"
)

# Counselor resolves
handler.resolve(
    crisis_id=record.crisis_id,
    resolved_by="counselor_001",
    resolution_notes="Met with student, safety plan created"
)
```

## Escalation Paths

| Path | Trigger | Action |
|------|---------|--------|
| COUNSELOR_ALERT | Default | Notify school counselor |
| ADMIN_ALERT | Counselor unavailable | Notify school admin |
| EMERGENCY_SERVICES | Imminent danger | 911 / crisis hotline |
| PARENT_NOTIFICATION | Per school policy | Notify parent/guardian |

## Event Payload Schema

```json
{
  "event_id": "evt_abc123",
  "event_type": "safety.crisis.detected",
  "timestamp": "2026-01-14T10:30:00Z",
  "source": "crisis-engine",
  "data": {
    "student_id_hash": "a3c4f9...",
    "session_id": "sess_xyz789",
    "risk_level": "CRISIS",
    "trigger_source": "safety_service",
    "trigger_keywords": ["kill myself"],
    "requires_human_intervention": true,
    "escalation_path": "counselor_alert",
    "school_id": "school_001"
  }
}
```

## Why Event-Driven? (ADR-004)

The Crisis Engine is decoupled from other services because:

1. **High Availability**: If Chat Service crashes, crisis alerts still fire
2. **Guaranteed Delivery**: Kinesis provides at-least-once delivery
3. **Audit Trail**: All events are logged for legal compliance
4. **Scalability**: Can handle burst of crisis events without blocking

## Metrics & Monitoring

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Time to Acknowledge | < 5 min | > 10 min |
| Time to Resolve | < 2 hours | > 4 hours |
| Event Processing Latency | < 1 sec | > 5 sec |
| Missed Crisis Rate | 0% | Any |
