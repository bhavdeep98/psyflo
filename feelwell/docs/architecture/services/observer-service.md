# Observer Service

## Purpose

The Observer Service implements the Analytical Monitor (Observer Agent) from the architecture spec. It performs real-time parsing of conversation history and maps utterances to clinical frameworks without exposing scoring to the student.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       OBSERVER SERVICE                               │
│                                                                      │
│  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   │
│  │ Message         │ → │ Clinical Marker │ → │ Risk Score      │   │
│  │ Analyzer        │   │ Detector        │   │ Calculator      │   │
│  │ (Layer 1)       │   │ (PHQ-9, GAD-7)  │   │                 │   │
│  └─────────────────┘   └─────────────────┘   └─────────────────┘   │
│           │                                           │             │
│           ▼                                           ▼             │
│  ┌─────────────────┐                        ┌─────────────────┐    │
│  │ Session         │                        │ CurrentSnapshot │    │
│  │ Summarizer      │                        │ (to MongoDB)    │    │
│  │ (Layer 2)       │                        └─────────────────┘    │
│  └─────────────────┘                                               │
│           │                                                         │
│           ▼                                                         │
│  ┌─────────────────┐                                               │
│  │ SessionSummary  │                                               │
│  │ (to PostgreSQL) │                                               │
│  └─────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
```

## Clinical Frameworks

### PHQ-9 (Depression)

Maps conversational language to DSM-5 criteria:

| Item | Criterion | Example Patterns |
|------|-----------|------------------|
| 1 | Anhedonia | "nothing is fun", "lost interest", "don't enjoy" |
| 2 | Depressed Mood | "feeling down", "hopeless", "empty inside" |
| 3 | Sleep | "can't sleep", "sleeping too much", "exhausted" |
| 4 | Fatigue | "no energy", "can't get out of bed", "drained" |
| 5 | Appetite | "not hungry", "eating too much", "forgot to eat" |
| 6 | Guilt | "hate myself", "worthless", "burden to everyone" |
| 7 | Concentration | "can't focus", "brain fog", "zoning out" |
| 8 | Psychomotor | "moving slow", "can't sit still", "restless" |
| 9 | Self-Harm | "hurt myself", "don't want to be here" (CRITICAL) |

### GAD-7 (Anxiety)

| Item | Criterion | Example Patterns |
|------|-----------|------------------|
| 1 | Nervous/Anxious | "so anxious", "on edge", "can't relax" |
| 2 | Can't Stop Worrying | "overthinking", "racing thoughts" |
| 3 | Worrying Too Much | "worried about", "freaking out" |
| 4 | Trouble Relaxing | "always tense", "never calm" |
| 5 | Restless | "can't sit still", "jittery" |
| 6 | Irritable | "snapping at", "short temper" |
| 7 | Afraid | "something bad will happen", "dread" |

## Key Components

### MessageAnalyzer (Layer 1)

Analyzes individual messages in real-time.

```python
from feelwell.services.observer_service.analyzer import MessageAnalyzer

analyzer = MessageAnalyzer()
snapshot = analyzer.analyze(
    message_id="msg_123",
    session_id="sess_456",
    student_id="student_789",
    text="Nothing feels fun anymore, I just sleep all day",
    safety_risk_score=0.3  # From Safety Service
)

# snapshot.risk_level = CAUTION
# snapshot.markers = [PHQ9 Item 1 (Anhedonia), PHQ9 Item 4 (Fatigue)]
```

### SessionSummarizer (Layer 2)

Aggregates all messages from a session.

```python
from feelwell.services.observer_service.session_summarizer import SessionSummarizer

summarizer = SessionSummarizer()
summary = summarizer.summarize(
    session_id="sess_456",
    student_id_hash="hash_abc",
    snapshots=[snapshot1, snapshot2, snapshot3],
    session_start=start_time,
    session_end=end_time
)

# summary.phq9_score = 7 (Moderate)
# summary.risk_trajectory = "escalating"
# summary.counselor_flag = True
```

## Data Models

### CurrentSnapshot (Layer 1)

```python
@dataclass(frozen=True)
class CurrentSnapshot:
    message_id: str
    session_id: str
    student_id_hash: str
    risk_score: float        # 0.0 to 1.0
    risk_level: RiskLevel
    markers: List[ClinicalMarker]
    timestamp: datetime
```

### SessionSummary (Layer 2)

```python
@dataclass(frozen=True)
class SessionSummary:
    session_id: str
    student_id_hash: str
    duration_minutes: int
    message_count: int
    start_risk_score: float
    end_risk_score: float
    phq9_score: Optional[int]    # 0-27
    gad7_score: Optional[int]    # 0-21
    risk_trajectory: str         # "stable", "improving", "escalating"
    counselor_flag: bool
```

## Counselor Flagging Logic

A session is flagged for counselor review if ANY of:

1. End risk score ≥ 0.5
2. Risk trajectory is "escalating"
3. PHQ-9 score ≥ 10 (moderate depression)
4. Self-harm marker detected (PHQ-9 Item 9)

## Integration with RAG

Session summaries feed into the RAG system for context-aware responses:

```
Previous sessions for student abc123_hash:
- Session 1: PHQ-9 = 4 (Minimal), trajectory = stable
- Session 2: PHQ-9 = 7 (Moderate), trajectory = escalating ⚠️

LLM Context: "This student's mood has been declining over 2 sessions.
Be attentive to signs of worsening mood."
```
