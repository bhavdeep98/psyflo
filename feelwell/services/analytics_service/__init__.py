"""Analytics Service: Aggregate reporting with privacy protection.

Per ADR-006: Mandatory k-anonymity for dashboard reports.
Suppress data if group size k < 5 to prevent reverse-engineering
individual student data from aggregated reports.

This service provides:
- Batch processing of interaction logs for mood trends
- K-anonymity enforcement on all aggregations
- School/district-level aggregate reports
- Dashboard data APIs for counselors

Endpoints:
- GET /health - Health check
- GET /ready - Readiness check
- GET /flagged-sessions - Get sessions flagged for counselor review
- GET /mood-trends - Aggregate mood trends by time period
- GET /school-overview - School-level risk overview
- POST /sessions - Add session summary
"""

from .k_anonymity import (
    KAnonymityEnforcer,
    AggregateResult,
    enforce_k_anonymity,
    K_ANONYMITY_THRESHOLD,
)
from .handler import (
    AnalyticsHandler,
    AnalyticsConfig,
    FlaggedSession,
    app,
)

__all__ = [
    "KAnonymityEnforcer",
    "AggregateResult",
    "enforce_k_anonymity",
    "K_ANONYMITY_THRESHOLD",
    "AnalyticsHandler",
    "AnalyticsConfig",
    "FlaggedSession",
    "app",
]
