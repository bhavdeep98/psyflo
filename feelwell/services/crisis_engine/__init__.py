"""Crisis Response Engine: High-priority alert orchestration.

Per ADR-004: Event-driven crisis response using Kinesis/EventBridge.
The "fire alarm" must be highly available and decoupled - if chat
crashes, crisis protocol still executes.

This engine:
1. Receives crisis events from Safety Service and Observer Service
2. Determines escalation path based on severity
3. Coordinates notification delivery
4. Maintains crisis event state machine

Endpoints:
- POST /crisis/safety - Handle Safety Service crisis
- POST /crisis/observer - Handle Observer threshold exceeded
- POST /crisis/<id>/acknowledge - Acknowledge crisis
- POST /crisis/<id>/resolve - Resolve crisis
- GET /crisis/active - List active crises
"""

from .handler import CrisisHandler, CrisisState, CrisisRecord
from .events import CrisisEvent, CrisisEventType, CrisisEventPublisher, EscalationPath

__all__ = [
    "CrisisHandler",
    "CrisisState",
    "CrisisRecord",
    "CrisisEvent",
    "CrisisEventType",
    "CrisisEventPublisher",
    "EscalationPath",
]
