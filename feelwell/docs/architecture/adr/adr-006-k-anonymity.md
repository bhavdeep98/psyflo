# ADR-006: Mandatory K-Anonymity for Dashboard Reports

## Status

Accepted

## Context

Feelwell provides aggregate reports to school counselors and administrators. Even without showing individual student data, small group sizes could allow re-identification. For example, if only one student in Grade 12 used the system, showing "Grade 12 average mood score" reveals that student's data.

## Decision

Suppress data if group size k < 5. All aggregation queries must check group size before returning results.

## Rationale

1. **Privacy Protection**: Prevent reverse-engineering individual data
2. **FERPA Compliance**: Aggregates must not reveal individuals
3. **Industry Standard**: k=5 is common in educational data
4. **Balance**: Maintains utility for most school sizes

## Consequences

### Positive

- Individual students cannot be identified from reports
- Compliant with educational data privacy standards
- Simple rule that's easy to audit
- Protects students in small groups

### Negative

- Limited utility for very small groups/classes
- Some schools may see many "suppressed" values
- Cannot provide grade-level data for small grades
- May frustrate administrators wanting detailed data

## Implementation

### K-Anonymity Enforcer

```python
from feelwell.services.analytics_service.k_anonymity import (
    KAnonymityEnforcer, K_ANONYMITY_THRESHOLD
)

enforcer = KAnonymityEnforcer(k_threshold=5)

result = enforcer.check_and_suppress(
    data={"avg_risk": 0.45},
    group_size=3,
    context="grade_12_risk_score"
)

if result.suppressed:
    # Return placeholder instead of actual data
    return {"avg_risk": None, "reason": result.suppression_reason}
```

### Aggregate with Anonymity

```python
# Automatically applies k-anonymity to all groups
results = enforcer.aggregate_with_anonymity(
    records=student_records,
    group_by="grade",
    aggregate_field="risk_score",
    aggregation="avg"
)

# Results for small groups are automatically suppressed
for grade, result in results.items():
    if result.suppressed:
        print(f"Grade {grade}: [Suppressed - fewer than 5 students]")
    else:
        print(f"Grade {grade}: {result.data:.2f}")
```

## Example Output

```
School Wellness Dashboard - Lincoln High School

Grade 9:  Average Mood Score: 3.2/5  (n=47)
Grade 10: Average Mood Score: 3.5/5  (n=52)
Grade 11: Average Mood Score: 3.1/5  (n=48)
Grade 12: [Data suppressed - fewer than 5 students used system]

Note: Data is suppressed when fewer than 5 students are in a group
to protect individual privacy.
```

## Edge Cases

| Scenario | Handling |
|----------|----------|
| New school (< 5 total users) | All data suppressed until threshold met |
| Single grade with < 5 users | That grade suppressed, others shown |
| Cross-school reports | Each school must meet threshold independently |
| Time-based reports | Each time period must meet threshold |

## Why K=5?

- **K=3**: Too low, easy to narrow down individuals
- **K=5**: Industry standard, good balance
- **K=10**: Too restrictive for small schools
- **K=20**: Would suppress most useful data
