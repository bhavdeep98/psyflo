# Analytics Service

## Purpose

The Analytics Service provides aggregate reporting with privacy protection. Per ADR-006, all reports enforce k-anonymity to prevent re-identification of individual students.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ANALYTICS SERVICE                                 │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     DATA SOURCES                                 │    │
│  │  Session Summaries │ Clinical Scores │ Crisis Events            │    │
│  │  (PostgreSQL)      │ (PostgreSQL)    │ (DynamoDB)               │    │
│  └────────────────────────────┬────────────────────────────────────┘    │
│                               │                                          │
│                               ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     ETL PIPELINE (AWS Glue)                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                               │                                          │
│                               ▼                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                     K-ANONYMITY ENFORCER                         │    │
│  │                     (Suppress if k < 5)                          │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                               │                                          │
│              ┌────────────────┼────────────────┐                        │
│              ▼                ▼                ▼                        │
│  ┌─────────────────┐  ┌─────────────┐  ┌─────────────────┐             │
│  │ School Dashboard│  │ District    │  │ Research        │             │
│  │ (Counselors)    │  │ Reports     │  │ Exports         │             │
│  └─────────────────┘  └─────────────┘  └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────┘
```

## K-Anonymity (ADR-006)

### What is K-Anonymity?

K-anonymity ensures that any individual in a dataset cannot be distinguished from at least k-1 other individuals. For Feelwell, k=5.

### Why K=5?

- Prevents reverse-engineering individual student data from aggregates
- Balances privacy with utility for small schools
- Industry standard for educational data

### Example

```
Grade 9: 47 students → Average PHQ-9: 4.2 ✅ (shown)
Grade 10: 52 students → Average PHQ-9: 5.1 ✅ (shown)
Grade 11: 3 students → Average PHQ-9: ??? ❌ (suppressed)
```

## Key Components

### KAnonymityEnforcer

```python
from feelwell.services.analytics_service.k_anonymity import (
    KAnonymityEnforcer, enforce_k_anonymity
)

enforcer = KAnonymityEnforcer(k_threshold=5)

# Check single aggregation
result = enforcer.check_and_suppress(
    data={"avg_risk": 0.45},
    group_size=3,
    context="grade_9_risk_score"
)

if result.suppressed:
    # Data not shown to protect privacy
    print(result.suppression_reason)
else:
    # Safe to display
    print(result.data)
```

### Aggregate with Anonymity

```python
# Aggregate risk scores by grade with k-anonymity
records = [
    {"grade": "9", "risk_score": 0.3},
    {"grade": "9", "risk_score": 0.4},
    # ... more records
]

results = enforcer.aggregate_with_anonymity(
    records=records,
    group_by="grade",
    aggregate_field="risk_score",
    aggregation="avg"
)

for grade, result in results.items():
    if result.suppressed:
        print(f"Grade {grade}: Data suppressed (n={result.group_size})")
    else:
        print(f"Grade {grade}: Avg risk = {result.data:.2f}")
```

## AggregateResult Schema

```python
@dataclass(frozen=True)
class AggregateResult:
    data: Optional[T]           # The aggregated value (None if suppressed)
    group_size: int             # Number of individuals
    suppressed: bool            # True if k-anonymity applied
    suppression_reason: str     # Explanation if suppressed
```

## Dashboard Reports

### School-Level Dashboard

| Metric | Aggregation | K-Anonymity |
|--------|-------------|-------------|
| Average mood score | By grade | Yes |
| Crisis events (count) | By week | Yes |
| Session duration | By grade | Yes |
| Counselor referral rate | By grade | Yes |

### District-Level Reports

| Report | Frequency | K-Anonymity |
|--------|-----------|-------------|
| School wellness comparison | Monthly | Yes (per school) |
| Trend analysis | Quarterly | Yes |
| Resource allocation | Annually | Yes |

## Batch Jobs

| Job | Schedule | Purpose |
|-----|----------|---------|
| Nightly Aggregation | 2 AM | Aggregate daily mood data |
| Weekly Trends | Sunday | Generate trend reports |
| Monthly Archive | 1st of month | Move old data to S3 Parquet |

## API Endpoints

```
GET  /analytics/dashboard/:schoolId
GET  /analytics/trends/:schoolId?period=30d
POST /analytics/generate-report
GET  /analytics/report/:reportId
```

## Privacy Guarantees

1. **No Individual Data**: Dashboard never shows single-student data
2. **K-Anonymity**: Groups < 5 are suppressed
3. **Aggregation Only**: Raw data never leaves the service
4. **Audit Trail**: All report access is logged
