# ADR-002: Segregation and Tiering of Logs

## Status

Accepted

## Context

Feelwell generates significant log volume across multiple categories:
- Application logs (debugging, performance)
- Interaction logs (conversation transcripts)
- Audit trail (compliance, legal)

Storing all logs in hot storage (OpenSearch/MongoDB) would cost ~$50k/month at scale. However, compliance requires 1-7+ year retention for certain log types.

## Decision

Implement tiered storage with automatic lifecycle policies:

| Log Type | Hot Storage | Warm Storage | Cold Storage |
|----------|-------------|--------------|--------------|
| Application | OpenSearch (30 days) | - | Deleted |
| Interaction | MongoDB (90 days) | S3 Parquet (7 years) | S3 Glacier |
| Audit Trail | QLDB (1 year) | PostgreSQL WORM | S3 Glacier Deep Archive |

## Rationale

1. **Cost Reduction**: $50k/month → $200/month for cold storage
2. **Compliance**: Meets FERPA/HIPAA retention requirements
3. **Performance**: Hot storage only for recent, frequently accessed data
4. **Legal**: Audit trail preserved for 7+ years

## Consequences

### Positive

- 99.6% cost reduction for log storage
- Compliance with retention requirements
- Fast access to recent data

### Negative

- Glacier retrieval takes up to 12 hours
- Increased complexity in log pipeline
- Must plan ahead for legal subpoenas

## Implementation

```python
# S3 Lifecycle Policy (Terraform)
resource "aws_s3_bucket_lifecycle_configuration" "interaction_logs" {
  bucket = aws_s3_bucket.interaction_logs.id

  rule {
    id     = "archive-to-glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "GLACIER"
    }

    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }

    expiration {
      days = 2555  # 7 years
    }
  }
}
```

## Trade-offs Accepted

- 12-hour retrieval time for archived logs is acceptable because:
  - Legal subpoenas typically have 30-day response windows
  - Clinical review rarely needs data older than 90 days
  - Cost savings justify the access delay
