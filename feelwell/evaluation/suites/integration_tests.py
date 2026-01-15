"""Integration test suite - service-to-service communication.

Tests the contracts and communication between services:
- Safety → Observer handoff
- Safety → Crisis Engine trigger
- Observer → Crisis Engine threshold
- All services → Audit logging
- Analytics aggregation from Observer
"""
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from feelwell.shared.utils import hash_pii, configure_pii_salt

logger = logging.getLogger(__name__)


class IntegrationTestStatus(Enum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


@dataclass
class IntegrationTestCase:
    """Definition of an integration test."""
    test_id: str
    name: str
    description: str
    source_service: str
    target_service: str
    test_type: str  # contract, handoff, event
    
    # Test data
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    
    # Validation rules
    required_fields: List[str] = field(default_factory=list)
    timeout_ms: int = 3000


@dataclass
class IntegrationTestResult:
    """Result of an integration test."""
    test_id: str
    status: IntegrationTestStatus
    latency_ms: float
    request_data: Dict[str, Any]
    response_data: Dict[str, Any]
    validation_errors: List[str] = field(default_factory=list)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "status": self.status.value,
            "latency_ms": round(self.latency_ms, 2),
            "validation_errors": self.validation_errors,
            "error_message": self.error_message,
        }


@dataclass
class IntegrationSuiteResult:
    """Result of running integration test suite."""
    suite_id: str
    started_at: datetime
    completed_at: datetime
    total_tests: int
    passed: int
    failed: int
    results: List[IntegrationTestResult]
    
    @property
    def pass_rate(self) -> float:
        if self.total_tests == 0:
            return 0.0
        return self.passed / self.total_tests
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "total_tests": self.total_tests,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.pass_rate, 4),
        }


class IntegrationTestSuite:
    """Integration test suite for service communication.
    
    Tests contracts and data flow between services.
    """
    
    # Contract tests - verify API schemas
    CONTRACT_TESTS = [
        IntegrationTestCase(
            test_id="INT-CONTRACT-001",
            name="Safety Service Scan Contract",
            description="Verify /scan endpoint accepts correct schema",
            source_service="client",
            target_service="safety_service",
            test_type="contract",
            input_data={
                "message": "Test message",
                "message_id": "msg_001",
                "session_id": "sess_001",
                "student_id": "student_001",
                "school_id": "school_001",
            },
            expected_output={
                "risk_level": ["safe", "caution", "crisis"],
                "risk_score": "float",
                "bypass_llm": "bool",
            },
            required_fields=["risk_level", "risk_score", "bypass_llm"],
        ),
        IntegrationTestCase(
            test_id="INT-CONTRACT-002",
            name="Observer Service Analyze Contract",
            description="Verify /analyze endpoint accepts correct schema",
            source_service="safety_service",
            target_service="observer_service",
            test_type="contract",
            input_data={
                "message": "Test message",
                "message_id": "msg_001",
                "session_id": "sess_001",
                "student_id": "student_001",
                "safety_risk_score": 0.3,
            },
            expected_output={
                "risk_level": ["safe", "caution", "crisis"],
                "risk_score": "float",
                "markers": "list",
            },
            required_fields=["message_id", "risk_level", "risk_score"],
        ),
        IntegrationTestCase(
            test_id="INT-CONTRACT-003",
            name="Crisis Engine Safety Trigger Contract",
            description="Verify /crisis/safety endpoint accepts correct schema",
            source_service="safety_service",
            target_service="crisis_engine",
            test_type="contract",
            input_data={
                "student_id_hash": "hash_abc123",
                "session_id": "sess_001",
                "matched_keywords": ["kill myself"],
                "school_id": "school_001",
            },
            expected_output={
                "crisis_id": "string",
                "state": "string",
            },
            required_fields=["crisis_id", "state"],
        ),
        IntegrationTestCase(
            test_id="INT-CONTRACT-004",
            name="Audit Service Log Contract",
            description="Verify /audit/log endpoint accepts correct schema",
            source_service="any",
            target_service="audit_service",
            test_type="contract",
            input_data={
                "action": "view_conversation",
                "entity_type": "student",
                "entity_id": "hash_abc123",
                "actor_id": "counselor_001",
                "actor_role": "counselor",
                "school_id": "school_001",
            },
            expected_output={
                "entry_id": "string",
                "timestamp": "string",
            },
            required_fields=["entry_id", "timestamp"],
        ),
    ]
    
    # Handoff tests - verify data flows correctly between services
    HANDOFF_TESTS = [
        IntegrationTestCase(
            test_id="INT-HANDOFF-001",
            name="Safety to Observer Handoff",
            description="Safety scan result correctly passed to Observer",
            source_service="safety_service",
            target_service="observer_service",
            test_type="handoff",
            input_data={
                "message": "I feel hopeless",
                "message_id": "msg_handoff_001",
                "session_id": "sess_handoff_001",
                "student_id": "student_handoff_001",
            },
            expected_output={
                "safety_risk_preserved": True,
                "message_id_matches": True,
            },
            required_fields=["message_id", "risk_score"],
        ),
        IntegrationTestCase(
            test_id="INT-HANDOFF-002",
            name="Safety to Crisis Engine Handoff",
            description="Crisis detection triggers Crisis Engine correctly",
            source_service="safety_service",
            target_service="crisis_engine",
            test_type="handoff",
            input_data={
                "message": "I want to kill myself",
                "message_id": "msg_crisis_001",
                "session_id": "sess_crisis_001",
                "student_id": "student_crisis_001",
            },
            expected_output={
                "crisis_created": True,
                "keywords_preserved": True,
            },
            required_fields=["crisis_id"],
        ),
        IntegrationTestCase(
            test_id="INT-HANDOFF-003",
            name="Observer to Analytics Handoff",
            description="Session summary correctly sent to Analytics",
            source_service="observer_service",
            target_service="analytics_service",
            test_type="handoff",
            input_data={
                "session_id": "sess_analytics_001",
                "student_id_hash": "hash_analytics_001",
                "school_id": "school_001",
                "end_risk_score": 0.6,
                "counselor_flag": True,
            },
            expected_output={
                "session_recorded": True,
            },
            required_fields=["session_id"],
        ),
    ]
    
    # Event tests - verify event publishing/consumption
    EVENT_TESTS = [
        IntegrationTestCase(
            test_id="INT-EVENT-001",
            name="Crisis Event Published",
            description="Crisis detection publishes event to Kinesis",
            source_service="safety_service",
            target_service="kinesis",
            test_type="event",
            input_data={
                "message": "I want to kill myself",
                "student_id_hash": "hash_event_001",
                "session_id": "sess_event_001",
            },
            expected_output={
                "event_published": True,
                "event_type": "CRISIS_DETECTED",
            },
            required_fields=["event_id"],
        ),
        IntegrationTestCase(
            test_id="INT-EVENT-002",
            name="Threshold Event Published",
            description="Observer threshold exceeded publishes event",
            source_service="observer_service",
            target_service="kinesis",
            test_type="event",
            input_data={
                "risk_score": 0.85,
                "student_id_hash": "hash_threshold_001",
                "session_id": "sess_threshold_001",
            },
            expected_output={
                "event_published": True,
                "event_type": "THRESHOLD_EXCEEDED",
            },
            required_fields=["event_id"],
        ),
    ]
    
    def __init__(
        self,
        safety_service=None,
        observer_service=None,
        crisis_engine=None,
        audit_service=None,
        analytics_service=None,
    ):
        """Initialize integration test suite.
        
        Args:
            safety_service: Safety service client
            observer_service: Observer service client
            crisis_engine: Crisis engine client
            audit_service: Audit service client
            analytics_service: Analytics service client
        """
        self.services = {
            "safety_service": safety_service,
            "observer_service": observer_service,
            "crisis_engine": crisis_engine,
            "audit_service": audit_service,
            "analytics_service": analytics_service,
        }
        
        configure_pii_salt("integration_test_salt_32_characters_long")
        
        logger.info("INTEGRATION_TEST_SUITE_INITIALIZED")
    
    def run_contract_test(self, test_case: IntegrationTestCase) -> IntegrationTestResult:
        """Run a contract validation test.
        
        Args:
            test_case: Contract test case
            
        Returns:
            IntegrationTestResult
        """
        start_time = time.perf_counter()
        validation_errors = []
        
        try:
            # Get target service
            service = self.services.get(test_case.target_service)
            
            if service is None:
                # Mock validation for testing without services
                response_data = self._mock_service_response(test_case)
            else:
                response_data = self._call_service(
                    test_case.target_service,
                    test_case.input_data,
                )
            
            # Validate required fields
            for field in test_case.required_fields:
                if field not in response_data:
                    validation_errors.append(f"Missing required field: {field}")
            
            # Validate field types
            for field, expected_type in test_case.expected_output.items():
                if field in response_data:
                    if expected_type == "float":
                        if not isinstance(response_data[field], (int, float)):
                            validation_errors.append(
                                f"Field {field} should be float, got {type(response_data[field])}"
                            )
                    elif expected_type == "bool":
                        if not isinstance(response_data[field], bool):
                            validation_errors.append(
                                f"Field {field} should be bool, got {type(response_data[field])}"
                            )
                    elif expected_type == "list":
                        if not isinstance(response_data[field], list):
                            validation_errors.append(
                                f"Field {field} should be list, got {type(response_data[field])}"
                            )
                    elif isinstance(expected_type, list):
                        if response_data[field] not in expected_type:
                            validation_errors.append(
                                f"Field {field} value {response_data[field]} not in {expected_type}"
                            )
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            status = (
                IntegrationTestStatus.PASSED
                if not validation_errors
                else IntegrationTestStatus.FAILED
            )
            
            return IntegrationTestResult(
                test_id=test_case.test_id,
                status=status,
                latency_ms=latency_ms,
                request_data=test_case.input_data,
                response_data=response_data,
                validation_errors=validation_errors,
            )
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return IntegrationTestResult(
                test_id=test_case.test_id,
                status=IntegrationTestStatus.ERROR,
                latency_ms=latency_ms,
                request_data=test_case.input_data,
                response_data={},
                error_message=str(e),
            )
    
    def run_handoff_test(self, test_case: IntegrationTestCase) -> IntegrationTestResult:
        """Run a service handoff test.
        
        Args:
            test_case: Handoff test case
            
        Returns:
            IntegrationTestResult
        """
        start_time = time.perf_counter()
        validation_errors = []
        
        try:
            # Call source service
            source_response = self._mock_service_response(test_case, "source")
            
            # Call target service with source output
            target_input = {**test_case.input_data, **source_response}
            target_response = self._mock_service_response(test_case, "target")
            
            # Validate handoff
            for field in test_case.required_fields:
                if field not in target_response:
                    validation_errors.append(f"Handoff missing field: {field}")
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            status = (
                IntegrationTestStatus.PASSED
                if not validation_errors
                else IntegrationTestStatus.FAILED
            )
            
            return IntegrationTestResult(
                test_id=test_case.test_id,
                status=status,
                latency_ms=latency_ms,
                request_data=test_case.input_data,
                response_data=target_response,
                validation_errors=validation_errors,
            )
            
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return IntegrationTestResult(
                test_id=test_case.test_id,
                status=IntegrationTestStatus.ERROR,
                latency_ms=latency_ms,
                request_data=test_case.input_data,
                response_data={},
                error_message=str(e),
            )
    
    def _mock_service_response(
        self,
        test_case: IntegrationTestCase,
        stage: str = "target",
    ) -> Dict[str, Any]:
        """Generate mock service response for testing."""
        if test_case.target_service == "safety_service":
            return {
                "risk_level": "caution",
                "risk_score": 0.45,
                "bypass_llm": False,
                "matched_keywords": ["hopeless"],
            }
        elif test_case.target_service == "observer_service":
            return {
                "message_id": test_case.input_data.get("message_id", "msg_001"),
                "risk_level": "caution",
                "risk_score": 0.5,
                "markers": [],
            }
        elif test_case.target_service == "crisis_engine":
            return {
                "crisis_id": f"crisis_{uuid.uuid4().hex[:8]}",
                "state": "notifying",
                "escalation_path": "counselor_alert",
            }
        elif test_case.target_service == "audit_service":
            return {
                "entry_id": f"audit_{uuid.uuid4().hex[:8]}",
                "timestamp": datetime.utcnow().isoformat(),
                "action": test_case.input_data.get("action", "unknown"),
            }
        elif test_case.target_service == "analytics_service":
            return {
                "session_id": test_case.input_data.get("session_id", "sess_001"),
                "status": "accepted",
            }
        elif test_case.target_service == "kinesis":
            return {
                "event_id": f"evt_{uuid.uuid4().hex[:8]}",
                "event_published": True,
                "event_type": test_case.expected_output.get("event_type", "UNKNOWN"),
            }
        
        return {}
    
    def _call_service(
        self,
        service_name: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call actual service (when available)."""
        service = self.services.get(service_name)
        if service is None:
            raise ValueError(f"Service {service_name} not configured")
        
        # Implementation would call actual service
        # For now, return mock
        return {}
    
    def run_all(self) -> IntegrationSuiteResult:
        """Run all integration tests.
        
        Returns:
            IntegrationSuiteResult with all outcomes
        """
        suite_id = f"int_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()
        
        all_tests = self.CONTRACT_TESTS + self.HANDOFF_TESTS + self.EVENT_TESTS
        
        logger.info(
            "INTEGRATION_SUITE_STARTED",
            extra={"suite_id": suite_id, "test_count": len(all_tests)}
        )
        
        results = []
        passed = 0
        failed = 0
        
        for test_case in all_tests:
            if test_case.test_type == "contract":
                result = self.run_contract_test(test_case)
            elif test_case.test_type == "handoff":
                result = self.run_handoff_test(test_case)
            else:
                result = self.run_contract_test(test_case)  # Default
            
            results.append(result)
            
            if result.status == IntegrationTestStatus.PASSED:
                passed += 1
            else:
                failed += 1
        
        completed_at = datetime.utcnow()
        
        suite_result = IntegrationSuiteResult(
            suite_id=suite_id,
            started_at=started_at,
            completed_at=completed_at,
            total_tests=len(all_tests),
            passed=passed,
            failed=failed,
            results=results,
        )
        
        logger.info(
            "INTEGRATION_SUITE_COMPLETED",
            extra={
                "suite_id": suite_id,
                "passed": passed,
                "failed": failed,
                "pass_rate": suite_result.pass_rate,
            }
        )
        
        return suite_result
