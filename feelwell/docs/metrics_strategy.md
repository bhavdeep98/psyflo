# System Metrics Strategy

This document outlines the key metrics required to monitor the health, performance, and safety of the Feelwell platform. Metrics are categorized by service and domain (Operational vs. Clinical).

## 1. Safety Service (Critical Path)
*Primary Goal: Ensure no harmful content reaches the LLM or user, with minimal latency.*

### Operational Metrics
- **`safety.scan.latency` (p50, p95, p99)**: Time taken to scan a message. Critical for chat responsiveness.
- **`safety.scan.throughput`**: Number of messages scanned per second.
- **`safety.error.count`**: Count of errors (fail-closed/fail-open events).
- **`safety.bypass_llm.count`**: Number of times the LLM was bypassed due to crisis detection.

### Functional/Safety Metrics
- **`safety.risk_level.distribution`**: Count of messages by risk level (SAFE, CAUTION, CRISIS).
- **`safety.rule.hit_count`**: Count of hits per specific regex pattern or keyword (helps tune rules).
- **`safety.false_positives`**: (Manual/Feedback derived) Count of safe messages flagged as risky.
- **`safety.false_negatives`**: (Critical) Count of risky messages that were missed.

## 2. Observer Service (Async Analysis)
*Primary Goal: accurately detect clinical markers and long-term trends without blocking chat.*

### Operational Metrics
- **`observer.analysis.lag`**: Time difference between message creation and analysis completion.
- **`observer.queue.depth`**: Number of messages waiting for analysis.
- **`observer.db.latency`**: Latency for storing snapshots in Postgres.
- **`observer.search.latency`**: Latency for RAG queries in OpenSearch.

### Clinical Metrics
- **`observer.marker.detected_count`**: Count of clinical markers detected, broken down by framework (PHQ-9, GAD-7).
- **`observer.sentiment.score.avg`**: Moving average of sentiment scores.
- **`observer.session.risk_trajectory`**: Variance in risk score from session start to end (Improving vs Escalating).

## 3. Crisis Engine (Incident Response)
*Primary Goal: Guarantee reliable escalation and timely resolution of critical incidents.*

### Operational Metrics
- **`crisis.event.processing_time`**: Time from receiving Kinesis event to creating a Crisis Record.
- **`crisis.notification.success_rate`**: Percentage of successful alerts sent (SMS/Email).
- **`crisis.notification.latency`**: Time taken to deliver an alert to a counselor.

### Business/Outcome Metrics
- **`crisis.time_to_acknowledge`**: Time from Alert Sent -> Counselor Acknowledges.
- **`crisis.time_to_resolve`**: Time from Acknowledge -> Incident Resolved.
- **`crisis.active_incidents`**: Gauge of currently open incidents.
- **`crisis.escalation.count`**: Count of incidents requiring external escalation (e.g., to 911).

## 4. Chat Service & LLM
*Primary Goal: Provide a responsive and engaging user experience.*

### Operational Metrics
- **`chat.response.latency`**: Total time from User Input -> Bot Response (End-to-End).
- **`llm.token.usage`**: Input/Output tokens (Cost tracking).
- **`llm.latency`**: Time taken by the model provider to generate response.
- **`llm.error.rate`**: API failures from the model provider.

## 5. Infrastructure (AWS)
- **ECS/Fargate**: CPU Utilization, Memory Utilization, Task Count (Running/Pending).
- **Kinesis**: Iterator Age (Lag), Write Provisioned Throughput Exceeded.
- **RDS/Postgres**: CPU, Free Storage Space, Connection Count.
- **ALB**: Request Count, 4xx/5xx Error Rates, Target Response Time.

## Dashboard Strategy
We should aggregate these into the following CloudWatch Dashboards:
1.  **Critical Safety View**: Safety Service latency + Crisis Active Incidents + Error Rates.
2.  **Clinical Operations View**: Risk distributions, marker trends, time-to-resolve stats.
3.  **Platform Health View**: CPU/Memory, DB health, Queue depths.
