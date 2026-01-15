# Data Pipeline & Storage Layers: Missing Components

**Date:** 2026-01-15
**Reference:** Original Architecture Document - "Data Pipeline & Storage Architecture"
**Current Status:** ❌ **0% Implemented - Completely Missing**

---

## Architecture Overview (From Design Document)

The architecture defines a **3-tier data flow**:

```
┌─────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER                           │
│  Amazon Kinesis Data Streams → Real-time event ingestion    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  PROCESSING LAYER                            │
│  AWS Lambda → PII Redaction Middleware                       │
│  AWS Glue → Batch ETL for analytics                          │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                             │
├─────────────────┬───────────────────┬───────────────────────┤
│  HOT STORAGE    │  WARM STORAGE     │  COLD STORAGE         │
│  (Immediate)    │  (30-90 days)     │  (1-7+ years)         │
├─────────────────┼───────────────────┼───────────────────────┤
│  Redis          │  DocumentDB       │  S3 Standard          │
│  RDS PostgreSQL │  S3 Standard      │  S3 Glacier           │
│  DynamoDB       │                   │  S3 Glacier Deep      │
│  OpenSearch     │                   │                       │
└─────────────────┴───────────────────┴───────────────────────┘
```

---

## 1. INGESTION LAYER - ❌ Completely Missing

### What the Architecture Defines

**Purpose:** Real-time event streaming from all microservices

**Technology:** Amazon Kinesis Data Streams

**Event Topics:**
1. `chat.message.sent` - Every student message
2. `safety.crisis.detected` - Crisis events from Safety Service
3. `observer.threshold.exceeded` - Risk escalation from Observer
4. `observer.session.completed` - Session summaries
5. `crisis.notification.required` - Alerts to counselors
6. `audit.event.logged` - All system actions

**Event Schema Example:**
```json
{
  "event_id": "evt_abc123",
  "event_type": "safety.crisis.detected",
  "timestamp": "2026-01-13T10:30:00Z",
  "source": "safety-service",
  "data": {
    "student_id_hash": "a3c4f9...",
    "session_id": "sess_xyz789",
    "risk_level": "CRISIS",
    "trigger_keywords": ["hurt myself"],
    "requires_human_intervention": true
  }
}
```

### Current Implementation: ❌ **NONE**

**Missing Components:**

#### 1.1 Kinesis Data Streams
- ❌ No Kinesis streams created
- ❌ No CDK stack for stream provisioning
- ❌ No shard configuration
- ❌ No retention period settings (24 hours - 7 days)
- ❌ No encryption configuration (KMS)

**Impact:** No real-time event streaming between services

**Effort:** 1-2 weeks
- Create CDK stack: `KinesisStreamStack`
- Define 6 streams (one per event topic)
- Configure retention: 24 hours minimum, 7 days for audit
- Enable encryption with KMS
- Set up IAM roles for producer/consumer access

#### 1.2 EventBridge Integration
- ❌ No EventBridge event bus configured
- ❌ No event routing rules
- ❌ No dead-letter queue for failed events
- ❌ No event replay capability

**Impact:** Cannot route events to multiple consumers

**Effort:** 1 week
- Create EventBridge event bus
- Define routing rules for each event type
- Configure SQS dead-letter queues
- Set up CloudWatch Events for monitoring

#### 1.3 Event Publishers (Service-Side)
- ⚠️ Code exists in services but not wired to real Kinesis
- ❌ No event schema validation
- ❌ No batch publishing optimization
- ❌ No failure retry logic

**Impact:** Services cannot publish events even if infrastructure exists

**Effort:** 2 weeks
- Wire Safety Service to Kinesis (currently skeleton)
- Wire Observer Service to EventBridge
- Wire Crisis Engine to notification topic
- Add schema validation (JSON Schema)
- Implement exponential backoff retry

---

## 2. PROCESSING LAYER - ❌ Completely Missing

### What the Architecture Defines

**Purpose:** Transform and enrich events before storage

**Components:**
1. **PII Redaction Lambda** - Remove sensitive data from logs
2. **Log Transformer Lambda** - Convert to Parquet format
3. **AWS Glue ETL Jobs** - Batch analytics processing

### Current Implementation: ❌ **NONE**

#### 2.1 PII Redaction Pipeline

**Architecture Design:**
```python
# Flow:
1. Raw event enters Kinesis stream
2. Lambda function intercepts
3. Detects PII fields: student_name, email, phone
4. Generates SHA-256 hash: student_id_hash
5. Replaces PII with hash in Application Logs only
6. Original data preserved in Interaction Logs (encrypted)
```

**Example Transformation:**
```python
# Before Redaction (Interaction Log)
{
  "student_id": "S12345",
  "student_name": "Jane Doe",
  "message": "I'm feeling really anxious today"
}

# After Redaction (Application Log)
{
  "student_id_hash": "a3c4f9...",
  "message": "I'm feeling really anxious today"
}
```

**Missing Components:**
- ❌ No Lambda function code for PII redaction
- ❌ No PII detection logic (regex patterns for names, emails, etc.)
- ❌ No SHA-256 hashing implementation
- ❌ No dual-path routing (original to Interaction Logs, redacted to Application Logs)
- ❌ No CloudWatch Logs integration

**Impact:**
- PII appears in CloudWatch Logs → FERPA violation
- Cannot safely debug production issues
- SOC 2 audit failure

**Effort:** 2-3 weeks
- **Week 1:** Build Lambda function
  - PII detection patterns (names, emails, SSNs, phone numbers)
  - SHA-256 hashing with salt
  - Kinesis consumer/producer
- **Week 2:** Dual-path routing
  - Original events → DocumentDB (Interaction Logs)
  - Redacted events → CloudWatch Logs (Application Logs)
  - S3 for both paths
- **Week 3:** Testing & validation
  - Test with 100+ PII variations
  - Verify hashing consistency
  - Performance testing (< 10ms per event)

**CDK Stack Needed:**
```typescript
// data-pipeline/lambdas/pii-redaction-stack.ts
- Lambda function (Python 3.11)
- Kinesis trigger
- IAM role (read Kinesis, write CloudWatch, write S3)
- Environment variables (SALT, KMS_KEY_ID)
- CloudWatch Logs (log group with 30-day retention)
```

#### 2.2 Log Transformer (JSON → Parquet)

**Architecture Design:**
- Convert JSON events to columnar Parquet format
- Compress for cost-efficient storage
- Partition by date and event type

**Missing Components:**
- ❌ No Lambda function for JSON → Parquet conversion
- ❌ No partitioning logic (year/month/day/hour)
- ❌ No compression configuration (Snappy/ZSTD)
- ❌ No schema evolution handling

**Impact:**
- Cannot query historical data efficiently
- Storage costs 10x higher (JSON vs Parquet)
- Analytics queries too slow

**Effort:** 2 weeks
- Build Lambda with PyArrow/Pandas
- Implement partitioning scheme
- Configure Snappy compression
- Test with 1M+ events

#### 2.3 AWS Glue ETL Jobs

**Architecture Design:**
- **Nightly Job:** Aggregate mood data across schools
- **Weekly Job:** Generate trend reports
- **Monthly Job:** Archive to S3 Glacier

**Missing Components:**
- ❌ No Glue job definitions
- ❌ No Glue Data Catalog (table schemas)
- ❌ No Glue Crawler (discover data)
- ❌ No job orchestration (Step Functions)
- ❌ No k-anonymity enforcement (suppress if k < 5)

**Impact:**
- No analytics data available
- No aggregated reports for counselors
- Cannot generate district-level insights

**Effort:** 3-4 weeks
- **Week 1:** Set up Glue Data Catalog
  - Define schemas for all event types
  - Configure crawlers for S3 data discovery
- **Week 2:** Build ETL jobs
  - Nightly aggregation (PySpark)
  - Weekly trend analysis
  - K-anonymity enforcement
- **Week 3:** Orchestration
  - Step Functions workflow
  - Error handling & retries
  - CloudWatch alarms
- **Week 4:** Testing
  - Test with production-scale data
  - Validate k-anonymity logic
  - Performance tuning

**Glue Jobs Needed:**
1. **nightly-mood-aggregation**
   - Input: Daily interaction logs (Parquet)
   - Output: School-level mood scores (RDS PostgreSQL)
   - K-anonymity: Suppress if < 5 students

2. **weekly-trend-analysis**
   - Input: Last 7 days aggregated data
   - Output: Trend reports (S3 + RDS)
   - Generate charts (matplotlib)

3. **monthly-archival**
   - Input: Events older than 90 days (S3 Standard)
   - Output: S3 Glacier Deep Archive
   - Lifecycle transition

---

## 3. STORAGE LAYER - ⚠️ Partially Missing

### What the Architecture Defines

**Three-tier storage strategy:**
- **Hot Storage (0-30 days):** Immediate access, high cost
- **Warm Storage (30-90 days):** Occasional access, medium cost
- **Cold Storage (90 days - 7+ years):** Rare access, low cost

### 3.1 Hot Storage (Immediate Access)

#### Redis (Session Caching) - ❌ Missing

**Architecture Design:**
- Cache active conversation contexts (last N messages)
- Store session tokens (JWT, 15-minute TTL)
- Cache compiled regex patterns for Safety Service

**Missing Components:**
- ❌ No ElastiCache Redis cluster
- ❌ No CDK stack: `RedisStack`
- ❌ No security group configuration
- ❌ No cluster mode vs. replication mode decision
- ❌ No eviction policy (LRU recommended)

**Impact:**
- Chat Service cannot cache conversation context
- Auth Service cannot cache session tokens
- Safety Service recompiles patterns on every request (slow)

**Effort:** 1 week
- Create ElastiCache Redis cluster (multi-AZ)
- Configure in VPC private subnet
- Set eviction policy: `allkeys-lru`
- Configure Redis 7.x with encryption in-transit
- Set up CloudWatch metrics

**CDK Stack:**
```typescript
// infrastructure/lib/stacks/database/redis-stack.ts
- ElastiCache Redis cluster
- 2 replicas (Multi-AZ)
- Instance type: cache.t3.micro (dev), cache.r6g.large (prod)
- Encryption: TLS in-transit, KMS at-rest
- Backup: Daily snapshots (7-day retention)
```

#### RDS PostgreSQL (Relational Data) - ❌ Missing

**Architecture Design:**
```sql
-- Databases:
1. auth_db - User accounts, roles, permissions
2. observer_db - Clinical scores, session summaries
3. analytics_db - Report metadata, aggregated trends
4. integration_db - Student rosters, sync logs
```

**Missing Components:**
- ❌ No RDS PostgreSQL instance
- ❌ No CDK stack: `PostgresStack`
- ❌ No database schema migrations
- ❌ No read replicas for analytics queries
- ❌ No automated backups configured
- ❌ No connection pooling (RDS Proxy)

**Impact:**
- Cannot store user accounts (Auth Service)
- Cannot persist clinical scores (Observer Service)
- Cannot store student rosters (Integration Service)
- No foundation for any relational data

**Effort:** 2-3 weeks
- **Week 1:** Create RDS instance
  - PostgreSQL 15.x
  - Multi-AZ deployment
  - Encryption with KMS
  - Automated backups (7-day retention)
- **Week 2:** Schema design & migrations
  - Alembic/Flyway migration framework
  - Define all tables (users, roles, clinical_scores, etc.)
  - Create indexes for performance
- **Week 3:** Read replicas & pooling
  - 1-2 read replicas for analytics queries
  - RDS Proxy for connection pooling
  - Monitoring & alarms

**Tables Needed (Minimum):**
```sql
-- auth_db
CREATE TABLE users (
  user_id UUID PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  role VARCHAR(50) NOT NULL, -- student, counselor, admin
  school_id UUID NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE roles (
  role_id UUID PRIMARY KEY,
  role_name VARCHAR(50) UNIQUE NOT NULL,
  permissions JSONB NOT NULL
);

-- observer_db
CREATE TABLE clinical_scores (
  score_id UUID PRIMARY KEY,
  student_id_hash VARCHAR(64) NOT NULL,
  session_id UUID NOT NULL,
  phq9_score FLOAT,
  gad7_score FLOAT,
  confidence FLOAT,
  scored_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE session_summaries (
  session_id UUID PRIMARY KEY,
  student_id_hash VARCHAR(64) NOT NULL,
  start_time TIMESTAMP NOT NULL,
  end_time TIMESTAMP,
  risk_trajectory VARCHAR(20), -- improving, stable, worsening
  summary_text TEXT
);

-- integration_db
CREATE TABLE student_rosters (
  student_id VARCHAR(100) PRIMARY KEY,
  school_id UUID NOT NULL,
  grade_level INT,
  sis_source VARCHAR(50), -- clever, classlink
  last_synced_at TIMESTAMP
);
```

#### DynamoDB (Crisis Events) - ❌ Missing

**Architecture Design:**
- Store crisis events (high write throughput)
- Store notification delivery logs
- Store audit trail entries (if QLDB not used)

**Missing Components:**
- ❌ No DynamoDB tables created
- ❌ No CDK definitions
- ❌ No partition key design
- ❌ No TTL configuration for auto-deletion
- ❌ No point-in-time recovery (PITR)

**Impact:**
- Crisis Engine cannot store events
- Notification Service cannot track delivery status
- No fast lookups for recent crises

**Effort:** 1 week
- Create 3 DynamoDB tables:
  1. `crisis_events` (partition key: `student_id_hash`, sort key: `timestamp`)
  2. `notification_logs` (partition key: `notification_id`)
  3. `audit_trail` (partition key: `entity_id`, sort key: `timestamp`)
- Configure on-demand capacity (production) or provisioned (dev)
- Enable PITR for crisis_events
- Set TTL: 2 years for warm data
- Enable DynamoDB Streams for event-driven processing

**Table Schema Example:**
```python
# crisis_events table
{
  "student_id_hash": "a3c4f9...",  # Partition key
  "timestamp": "2026-01-15T10:30:00Z",  # Sort key
  "event_id": "evt_abc123",
  "risk_level": "CRISIS",
  "trigger_keywords": ["hurt myself"],
  "escalation_status": "NOTIFIED",
  "counselor_id": "counselor_xyz",
  "acknowledged_at": "2026-01-15T10:32:00Z",
  "ttl": 1735689000  # Auto-delete after 2 years
}
```

#### OpenSearch (Vector Embeddings for RAG) - ❌ Missing

**Architecture Design:**
- Store message embeddings for semantic search
- Enable Retrieval-Augmented Generation (RAG)
- Support "find similar conversations" feature

**Missing Components:**
- ❌ No OpenSearch cluster
- ❌ No CDK stack: `OpenSearchStack`
- ❌ No index mappings for vector fields
- ❌ No k-NN plugin configuration
- ❌ No embedding generation pipeline

**Impact:**
- Observer Service cannot do semantic analysis
- No RAG-based context retrieval
- Cannot find similar past conversations

**Effort:** 2-3 weeks
- **Week 1:** Deploy OpenSearch cluster
  - 3 data nodes (Multi-AZ)
  - 1 master node
  - Encryption at-rest (KMS) and in-transit (TLS)
  - VPC private subnet
- **Week 2:** Configure for vector search
  - Install k-NN plugin
  - Define index mapping with dense_vector field
  - Test with HNSW algorithm
- **Week 3:** Integrate with Observer Service
  - Generate embeddings (SentenceTransformers)
  - Index messages in real-time
  - Build similarity search API

**Index Mapping:**
```json
{
  "mappings": {
    "properties": {
      "message_id": { "type": "keyword" },
      "student_id_hash": { "type": "keyword" },
      "message_text": { "type": "text" },
      "embedding": {
        "type": "dense_vector",
        "dims": 768,  # BERT-base output size
        "index": true,
        "similarity": "cosine"
      },
      "risk_score": { "type": "float" },
      "timestamp": { "type": "date" }
    }
  }
}
```

### 3.2 Warm Storage (30-90 Days) - ❌ Missing

#### DocumentDB (Conversation History) - ❌ Missing

**Architecture Design:**
- Store full conversation sessions
- Keep last 90 days in hot tier
- Query by session_id or student_id_hash

**Missing Components:**
- ❌ No DocumentDB cluster
- ❌ No CDK stack: `DocumentDbStack`
- ❌ No collection schema design
- ❌ No backup/restore configuration
- ❌ No change streams for real-time updates

**Impact:**
- Chat Service cannot persist conversations
- No conversation history for counselors
- Cannot resume interrupted sessions

**Effort:** 2 weeks
- Create DocumentDB cluster (MongoDB-compatible)
- Configure multi-AZ with 2 replicas
- Enable encryption with KMS
- Define collections: `conversations`, `messages`, `sessions`
- Set up automated backups (7-day retention)
- Enable change streams for event-driven processing

**Collection Schema:**
```javascript
// conversations collection
{
  "_id": "sess_xyz789",
  "student_id_hash": "a3c4f9...",
  "school_id": "school_abc",
  "started_at": ISODate("2026-01-15T10:00:00Z"),
  "ended_at": ISODate("2026-01-15T10:45:00Z"),
  "status": "completed",  // active, completed, abandoned
  "messages": [
    {
      "message_id": "msg_001",
      "role": "student",
      "content": "I'm feeling anxious today",
      "timestamp": ISODate("2026-01-15T10:01:00Z"),
      "safety_scan": {
        "risk_level": "safe",
        "keywords_matched": []
      }
    },
    {
      "message_id": "msg_002",
      "role": "assistant",
      "content": "I hear you're feeling anxious. Can you tell me more?",
      "timestamp": ISODate("2026-01-15T10:02:00Z")
    }
  ],
  "clinical_summary": {
    "phq9_score": 8.5,
    "gad7_score": 12.0,
    "risk_trajectory": "stable"
  }
}
```

#### S3 Standard (Log Archives) - ❌ Missing

**Architecture Design:**
- Store events 30-90 days old
- Parquet format for efficient querying
- Partitioned by date and event type

**Missing Components:**
- ❌ No S3 buckets created
- ❌ No lifecycle policies configured
- ❌ No partition structure
- ❌ No versioning enabled
- ❌ No access logging

**Impact:**
- No warm storage tier
- Cannot query historical events
- No cost optimization

**Effort:** 1 week
- Create S3 buckets:
  - `feelwell-interaction-logs-{env}`
  - `feelwell-application-logs-{env}`
  - `feelwell-audit-trail-{env}`
- Configure lifecycle policies (30-day → Warm, 90-day → Cold)
- Set up partitioning: `s3://bucket/year=2026/month=01/day=15/hour=10/`
- Enable versioning for compliance
- Configure server-side encryption (SSE-KMS)
- Set up S3 access logs for auditing

### 3.3 Cold Storage (90 Days - 7+ Years) - ❌ Missing

#### S3 Glacier / Glacier Deep Archive - ❌ Missing

**Architecture Design:**
- Archive logs older than 90 days
- 7-year retention for FERPA compliance
- Retrieval time: 12-48 hours acceptable

**Missing Components:**
- ❌ No Glacier vault created
- ❌ No lifecycle transition rules (S3 Standard → Glacier → Deep Archive)
- ❌ No vault lock policies (WORM - Write Once Read Many)
- ❌ No retrieval testing

**Impact:**
- No long-term archival
- FERPA/COPPA compliance violation (7-year retention required)
- No disaster recovery for historical data

**Effort:** 1 week
- Configure S3 lifecycle policies:
  - Day 0-30: S3 Standard (Hot)
  - Day 30-90: S3 Standard-IA (Warm)
  - Day 90-365: S3 Glacier Instant Retrieval
  - Day 365+: S3 Glacier Deep Archive (up to 7 years)
- Set up Glacier Vault Lock (prevent deletion)
- Test retrieval process (Glacier: 1-5 hours, Deep Archive: 12-48 hours)
- Document retrieval procedures for compliance audits

**Lifecycle Policy Example:**
```json
{
  "Rules": [
    {
      "Id": "InteractionLogArchival",
      "Status": "Enabled",
      "Filter": { "Prefix": "interaction-logs/" },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "STANDARD_IA"
        },
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        },
        {
          "Days": 365,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ],
      "Expiration": {
        "Days": 2555  // 7 years
      }
    }
  ]
}
```

---

## 4. Log Retention & Compliance - ❌ Missing

### What the Architecture Defines

| Log Type | Retention | Hot Storage | Cold Storage | Purpose |
|----------|-----------|-------------|--------------|---------|
| **Application Logs** | 30 days | OpenSearch | None | Debugging, performance |
| **Interaction Logs** | 1-7 years | DocumentDB (90 days) | S3 Glacier | Clinical review, safety audits |
| **Audit Trail** | 7+ years (permanent) | QLDB (1 year) | S3 Glacier Deep | Legal compliance, forensics |
| **Crisis Events** | 10 years | DynamoDB (2 years) | S3 Glacier | Legal liability, incident review |
| **Clinical Scores** | 7 years | RDS PostgreSQL | S3 Parquet | Longitudinal research, outcomes |

### Current Implementation: ❌ **NONE**

**Missing:**
- ❌ No retention policies automated
- ❌ No lifecycle transitions configured
- ❌ No compliance monitoring (AWS Config rules)
- ❌ No archival job automation
- ❌ No retrieval testing

**Impact:** **CRITICAL**
- FERPA violation: No 7-year student record retention
- COPPA violation: Cannot prove data deletion after parental request
- SOC 2 failure: No evidence of data lifecycle management
- Legal liability: Cannot retrieve logs for lawsuits/investigations

**Effort:** 2 weeks
- Create AWS Config rules to enforce retention
- Build compliance dashboard showing retention status
- Automate archival with Step Functions
- Test retrieval from all tiers
- Document for SOC 2 auditors

---

## 5. Missing AWS Config Rules (Compliance Monitoring)

### Architecture Design

**Purpose:** Continuously monitor compliance

**Rules Needed:**
- `s3-bucket-encryption-enabled`
- `rds-encryption-enabled`
- `cloudtrail-enabled`
- `vpc-flow-logs-enabled`
- `required-tags` (e.g., "DataClassification:PHI")

### Current Implementation: ❌ **NONE**

**Missing:**
- ❌ No AWS Config enabled
- ❌ No compliance rules configured
- ❌ No alerting on violations
- ❌ No remediation automation

**Effort:** 1 week
- Enable AWS Config in account
- Deploy 10+ compliance rules
- Configure SNS alerts for violations
- Set up auto-remediation (e.g., re-encrypt unencrypted buckets)

---

## Summary: Data Pipeline & Storage Gaps

### Components Missing (All)

| Component | Status | Effort | Priority |
|-----------|--------|--------|----------|
| **Kinesis Data Streams** | ❌ Not started | 1-2 weeks | 🔴 Critical |
| **EventBridge** | ❌ Not started | 1 week | 🔴 Critical |
| **PII Redaction Lambda** | ❌ Not started | 2-3 weeks | 🔴 Critical |
| **Log Transformer Lambda** | ❌ Not started | 2 weeks | 🟠 High |
| **AWS Glue ETL Jobs** | ❌ Not started | 3-4 weeks | 🟡 Medium |
| **Redis Cluster** | ❌ Not started | 1 week | 🔴 Critical |
| **RDS PostgreSQL** | ❌ Not started | 2-3 weeks | 🔴 Critical |
| **DynamoDB Tables** | ❌ Not started | 1 week | 🔴 Critical |
| **OpenSearch Cluster** | ❌ Not started | 2-3 weeks | 🟠 High |
| **DocumentDB Cluster** | ❌ Not started | 2 weeks | 🔴 Critical |
| **S3 Buckets + Lifecycle** | ❌ Not started | 1 week | 🔴 Critical |
| **Glacier Archival** | ❌ Not started | 1 week | 🔴 Critical (compliance) |
| **AWS Config Rules** | ❌ Not started | 1 week | 🟠 High |

**Total Effort:** **19-28 weeks (5-7 months)**

---

## Impact Assessment

### Without Data Pipeline & Storage:

**Functionality Impacts:**
- ❌ No data persistence → System is stateless
- ❌ No conversation history → Cannot resume sessions
- ❌ No clinical scores → Cannot track student progress
- ❌ No user accounts → Cannot authenticate
- ❌ No event streaming → Services cannot communicate
- ❌ No analytics → Cannot generate reports

**Compliance Impacts:** 🔴 **CRITICAL**
- ❌ **FERPA violation:** No 7-year student record retention
- ❌ **COPPA violation:** Cannot prove data deletion
- ❌ **SOC 2 failure:** No audit trail, no data lifecycle management
- ❌ **PII exposure:** No redaction → PII in logs → regulatory fines

**Business Impacts:**
- ❌ Cannot deploy to production
- ❌ Cannot onboard customers
- ❌ Cannot demonstrate compliance to districts
- ❌ Cannot generate revenue

---

## Implementation Priority

### Phase 1: Critical Storage (Weeks 1-6)

**Enables:** Basic functionality

1. ✅ RDS PostgreSQL (2-3 weeks) - User accounts, clinical scores
2. ✅ DocumentDB (2 weeks) - Conversation persistence
3. ✅ Redis (1 week) - Session caching
4. ✅ DynamoDB (1 week) - Crisis events

**After Phase 1:** Services can persist data

### Phase 2: Event Infrastructure (Weeks 7-10)

**Enables:** Inter-service communication

1. ✅ Kinesis Streams (2 weeks) - Event ingestion
2. ✅ EventBridge (1 week) - Event routing
3. ✅ Wire services to events (1 week)

**After Phase 2:** Event-driven architecture functional

### Phase 3: Compliance & Processing (Weeks 11-18)

**Enables:** Regulatory compliance

1. ✅ PII Redaction Lambda (2-3 weeks) - FERPA compliance
2. ✅ S3 + Lifecycle Policies (1 week) - Data retention
3. ✅ Glacier Archival (1 week) - 7-year retention
4. ✅ AWS Config Rules (1 week) - Compliance monitoring
5. ✅ Log Transformer (2 weeks) - Cost optimization

**After Phase 3:** Compliance-ready

### Phase 4: Analytics (Weeks 19-24)

**Enables:** Reporting & insights

1. ✅ OpenSearch (2-3 weeks) - RAG/semantic search
2. ✅ AWS Glue ETL (3-4 weeks) - Analytics pipeline

**After Phase 4:** Full data pipeline operational

---

## Cost Estimates (Monthly)

### Hot Storage
- Redis (cache.r6g.large x2): $300/month
- RDS PostgreSQL (db.r6g.large x2): $600/month
- DynamoDB (on-demand, 10M writes): $125/month
- DocumentDB (db.r5.large x3): $800/month
- OpenSearch (r6g.large.search x3): $600/month

**Subtotal:** ~$2,425/month

### Warm/Cold Storage
- S3 Standard (100 GB): $3/month
- S3 Glacier (1 TB): $4/month
- S3 Deep Archive (10 TB): $10/month

**Subtotal:** ~$17/month

### Processing
- Kinesis (6 streams, 1 shard each): $54/month
- Lambda (1M invocations): $0.20/month
- Glue (10 DPU-hours/day): $132/month

**Subtotal:** ~$186/month

### **Total:** ~$2,628/month for production
- Dev environment: ~$800/month (smaller instances)

---

## Recommendations

### Immediate Actions (Next Sprint)

1. ✅ **Start with RDS PostgreSQL** - Foundation for all relational data
2. ✅ **Deploy DocumentDB** - Chat Service blocked without it
3. ✅ **Set up S3 buckets** - Quick win, enables log storage
4. ✅ **Create Kinesis streams** - Enables event-driven architecture

### Parallel Work Streams

**Team 1: Storage Layer**
- RDS, DocumentDB, Redis, DynamoDB

**Team 2: Event Infrastructure**
- Kinesis, EventBridge, Lambda consumers

**Team 3: Compliance**
- PII redaction, lifecycle policies, AWS Config

### Decision Points

1. **QLDB vs. PostgreSQL for audit trail?**
   - QLDB: Cryptographically verifiable, immutable
   - PostgreSQL: Simpler, cheaper, good enough?
   - **Recommendation:** Start with PostgreSQL + WORM, migrate to QLDB if SOC 2 requires

2. **OpenSearch vs. Pinecone for vector search?**
   - OpenSearch: Self-managed, AWS-native
   - Pinecone: Managed, easier
   - **Recommendation:** OpenSearch for data residency/compliance

3. **Build PII redaction or use AWS Comprehend?**
   - Custom Lambda: Full control, cheaper at scale
   - Comprehend: Faster to market, more accurate
   - **Recommendation:** Comprehend for MVP, custom Lambda for cost optimization later

---

## Conclusion

The data pipeline and storage layers are **0% implemented** despite being critical infrastructure.

**Blockers:**
- ❌ No persistence → System cannot function
- ❌ No event streams → Services cannot communicate
- ❌ No compliance → Cannot deploy to schools

**Timeline:** 5-7 months for complete implementation

**Recommendation:** **Start immediately** with Phase 1 (RDS, DocumentDB, Redis, DynamoDB) as these are **hard blockers** for service deployment.

---

**Document prepared by:** Claude (AI Assistant)
**Next steps:** Assign Phase 1 work to infrastructure team, prioritize RDS + DocumentDB
