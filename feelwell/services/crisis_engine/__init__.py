"""Crisis Response Engine: High-priority alert orchestration.

Per ADR-004: Event-driven crisis response using Kinesis/EventBridge.
The "fire alarm" must be highly available and decoupled - if chat
crashes, crisis protocol still executes.

This engine:
1. Receives crisis events from Safety Service and Observer Service
2. Determines escalation path based on severity
3. Coordinates notification delivery
4. Maintains crisis event state machine
"""
