"""K-anonymity enforcement per ADR-006.

Suppress data if group size k < 5 to prevent reverse-engineering
individual student data from aggregated reports.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypeVar, Generic

logger = logging.getLogger(__name__)

# Minimum group size for k-anonymity
K_ANONYMITY_THRESHOLD = 5

T = TypeVar('T')


@dataclass(frozen=True)
class AggregateResult(Generic[T]):
    """Result of an aggregation query with k-anonymity applied.
    
    Attributes:
        data: The aggregated data (None if suppressed)
        group_size: Number of individuals in the group
        suppressed: True if data was suppressed due to k-anonymity
        suppression_reason: Explanation if suppressed
    """
    data: Optional[T]
    group_size: int
    suppressed: bool
    suppression_reason: Optional[str] = None


class KAnonymityEnforcer:
    """Enforces k-anonymity on aggregated data.
    
    Per ADR-006: All dashboard reports must suppress data
    when group size is below threshold.
    """
    
    def __init__(self, k_threshold: int = K_ANONYMITY_THRESHOLD):
        """Initialize enforcer.
        
        Args:
            k_threshold: Minimum group size (default 5)
        """
        self.k_threshold = k_threshold
        
        logger.info(
            "K_ANONYMITY_ENFORCER_INITIALIZED",
            extra={"k_threshold": k_threshold}
        )
    
    def check_and_suppress(
        self,
        data: T,
        group_size: int,
        context: Optional[str] = None,
    ) -> AggregateResult[T]:
        """Check group size and suppress if below threshold.
        
        Args:
            data: The aggregated data to potentially suppress
            group_size: Number of individuals in the group
            context: Description of the query for logging
            
        Returns:
            AggregateResult with data or suppression info
            
        Logs:
            - K_ANONYMITY_SUPPRESSED: When data is suppressed
            - K_ANONYMITY_PASSED: When data passes threshold
        """
        if group_size < self.k_threshold:
            logger.warning(
                "K_ANONYMITY_SUPPRESSED",
                extra={
                    "group_size": group_size,
                    "k_threshold": self.k_threshold,
                    "context": context,
                    "action": "DATA_SUPPRESSED",
                }
            )
            return AggregateResult(
                data=None,
                group_size=group_size,
                suppressed=True,
                suppression_reason=(
                    f"Group size ({group_size}) below k-anonymity "
                    f"threshold ({self.k_threshold})"
                ),
            )
        
        logger.info(
            "K_ANONYMITY_PASSED",
            extra={
                "group_size": group_size,
                "k_threshold": self.k_threshold,
                "context": context,
            }
        )
        return AggregateResult(
            data=data,
            group_size=group_size,
            suppressed=False,
        )
    
    def aggregate_with_anonymity(
        self,
        records: List[Dict[str, Any]],
        group_by: str,
        aggregate_field: str,
        aggregation: str = "avg",
    ) -> Dict[str, AggregateResult]:
        """Aggregate records with k-anonymity enforcement.
        
        Args:
            records: List of records to aggregate
            group_by: Field to group by (e.g., "grade_level")
            aggregate_field: Field to aggregate (e.g., "risk_score")
            aggregation: Aggregation type ("avg", "count", "sum")
            
        Returns:
            Dictionary mapping group values to AggregateResult
        """
        # Group records
        groups: Dict[str, List[float]] = {}
        for record in records:
            key = str(record.get(group_by, "unknown"))
            value = record.get(aggregate_field)
            if value is not None:
                if key not in groups:
                    groups[key] = []
                groups[key].append(float(value))
        
        # Aggregate with k-anonymity check
        results: Dict[str, AggregateResult] = {}
        for key, values in groups.items():
            group_size = len(values)
            
            if aggregation == "avg":
                agg_value = sum(values) / len(values) if values else 0
            elif aggregation == "count":
                agg_value = len(values)
            elif aggregation == "sum":
                agg_value = sum(values)
            else:
                agg_value = sum(values) / len(values) if values else 0
            
            results[key] = self.check_and_suppress(
                data=agg_value,
                group_size=group_size,
                context=f"{aggregation}({aggregate_field}) by {group_by}={key}",
            )
        
        return results


def enforce_k_anonymity(
    data: T,
    group_size: int,
    k_threshold: int = K_ANONYMITY_THRESHOLD,
) -> AggregateResult[T]:
    """Convenience function for one-off k-anonymity checks.
    
    Args:
        data: Data to potentially suppress
        group_size: Number of individuals in group
        k_threshold: Minimum group size
        
    Returns:
        AggregateResult with data or suppression info
    """
    enforcer = KAnonymityEnforcer(k_threshold)
    return enforcer.check_and_suppress(data, group_size)
