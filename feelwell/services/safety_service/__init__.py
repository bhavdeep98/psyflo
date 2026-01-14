"""Safety Service: Deterministic guardrails and crisis detection.

ADR-001: Hard-coded regex/NLP filter layer bypasses LLM for high-risk inputs.
This service is the first line of defense - every message passes through here
BEFORE reaching the LLM.
"""
