---
inclusion: always
---

# Feelwell Code Philosophy & Engineering Principles

This document defines the coding standards and engineering principles for the Feelwell platform. All generated code MUST adhere to these principles.

## Context
- **Timeline**: Couple of months to MVP
- **Stakes**: Mental health + minors = zero tolerance for bugs
- **Team**: Enable "vibe coding" without sacrificing safety
- **Complexity**: Multi-service architecture with compliance requirements

## Core Principles

### 1. Explicit Over Clever
- Write traceable, self-documenting code
- Avoid list comprehensions for complex logic
- Add docstrings explaining purpose, returns, and logging behavior
- When a crisis is missed, you need to trace exactly what happened

```python
# ✅ GOOD: Explicit and traceable
def process_student_messages(messages: List[Message]) -> List[ValidMessage]:
    """Filters messages to only include valid, non-empty entries.
    
    Returns: List of messages that passed validation
    Logs: Invalid messages logged to CloudWatch with reason
    """
    valid_messages = []
    for message in messages:
        if not message:
            logger.warning("Received empty message", extra={"context": "process_student_messages"})
            continue
        if not validate_message(message):
            logger.warning("Message failed validation", extra={"message_id": message.id, "reason": "validation_failed"})
            continue
        valid_messages.append(message)
    return valid_messages
```

### 2. Fail Loud, Fail Early
- Never use bare `except:` clauses
- Never return `None` to indicate errors silently
- Always raise specific, documented exceptions
- Log errors with context before raising

```python
# ✅ GOOD: Explicit error handling
def get_student_age(student_id: str) -> int:
    """Retrieves student age for COPPA compliance checks.
    
    Raises:
        StudentNotFoundError: If student_id doesn't exist in database
        DatabaseConnectionError: If unable to connect to RDS
    """
    try:
        student = db.query(Student).filter_by(id=student_id).one()
        return student.age
    except NoResultFound:
        logger.error("Student not found", extra={"student_id_hash": hash_pii(student_id)})
        raise StudentNotFoundError(f"No student found with ID: {student_id}")
    except DBAPIError as e:
        logger.critical("Database connection failed", extra={"error": str(e)})
        raise DatabaseConnectionError("Unable to query student database")
```

### 3. Make Illegal States Unrepresentable
- Use Enums for fixed sets of values (risk levels, statuses)
- Use type hints everywhere
- Let the type system catch bugs at compile time

```python
# ✅ GOOD: Enums make invalid states impossible
from enum import Enum

class RiskLevel(Enum):
    SAFE = "safe"
    CAUTION = "caution"
    CRISIS = "crisis"

def handle_message(message: Message, risk_level: RiskLevel):
    if risk_level == RiskLevel.CRISIS:
        trigger_crisis()
```

### 4. No Magic Numbers or Strings
- Define named constants with documentation
- Reference clinical guidelines in comments
- One place to update thresholds

```python
# ✅ GOOD: Named constants with documentation
class ClinicalThresholds:
    """Clinical severity thresholds based on PHQ-9 scoring guidelines.
    Source: https://www.apa.org/depression-guideline/patient-health-questionnaire.pdf
    """
    LOW_SEVERITY = 4
    MODERATE_SEVERITY = 9
    HIGH_SEVERITY = 14
    CRISIS_THRESHOLD = 10
```

## Architecture Patterns

### Dependency Injection for Testability
```python
# ✅ GOOD: Easy to test (inject mocks)
class ChatService:
    def __init__(self, db: Database, llm: LLMClient, logger: Logger):
        self.db = db
        self.llm = llm
        self.logger = logger
```

### Command-Query Separation
- Commands (writes): Return None or status, have side effects
- Queries (reads): Return data, no side effects
- If a function returns data, it shouldn't modify state

### Single Responsibility per File
- If you can't describe what a file does in one sentence, it's doing too much
- Separate: handlers, services, repositories, models, utils

## Safety-Critical Code Standards

### Crisis Path Must Be Obvious
- Linear, traceable flow for crisis detection
- Step-by-step with logging at each stage
- Code IS the documentation for incident review

### Immutable by Default
```python
# ✅ GOOD: Immutable data structures
@dataclass(frozen=True)
class ConversationSession:
    session_id: str
    student_id: str
    messages: List[Message] = field(default_factory=list)
    
    def with_message(self, new_message: Message) -> 'ConversationSession':
        """Returns NEW session with message added. Original unchanged."""
        return ConversationSession(
            session_id=self.session_id,
            student_id=self.student_id,
            messages=[*self.messages, new_message]
        )
```

### Always Log Before and After Critical Operations
```python
logger.info("ESCALATION_STARTED", extra={...})
try:
    # operation
    logger.info("ESCALATION_SUCCESS_PRIMARY", extra={...})
except Exception as e:
    logger.error("ESCALATION_FAILED_PRIMARY", extra={...})
    # fallback
    logger.info("ESCALATION_SUCCESS_FALLBACK", extra={...})
```

## Compliance Requirements

### PII Handling
- Never log raw PII - use `hash_pii()` for student IDs in logs
- Audit events required for all data access
- COPPA consent must be checked before accessing student data

### Logging Standards
- Use `logger.info`, `logger.warning`, `logger.error`, `logger.critical`
- Never use `print()` statements
- Always include `extra={}` dict with context
- Critical safety functions use `logger.critical`

## Testing Requirements

### Coverage Thresholds
- Overall: 80% minimum
- Safety-critical code (`safety_service/`, `crisis_detector.py`): 100% required
- Include adversarial test cases for safety code

### Test Structure
```python
def test_send_message():
    mock_db = MockDatabase()
    mock_llm = MockLLM(response="I'm here to help")
    service = ChatService(db=mock_db, llm=mock_llm, logger=MockLogger())
    
    response = service.send_message(Message("I'm sad"))
    
    assert response.text == "I'm here to help"
    assert mock_db.save_called == True
```

## The Litmus Test

Can a new engineer, on day 1, looking at a random file, answer these questions in 60 seconds?

1. What does this file do?
2. What happens if this fails?
3. Where would I add a log statement to debug this?

**If yes → Good code. If no → Refactor.**
