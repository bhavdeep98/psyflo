"""Observer Service: Clinical pattern analysis and sentiment scoring.

This service implements the Analytical Monitor (Observer Agent) from the
architecture spec. It performs real-time parsing of conversation history
and maps utterances to clinical frameworks (PHQ-9, GAD-7, C-SSRS).

Key responsibilities:
- Layer 1: Real-time sentiment analysis on every message
- Layer 2: Session-level clinical marker aggregation
- Layer 3: Longitudinal trend tracking (via Analytics Service)
"""
