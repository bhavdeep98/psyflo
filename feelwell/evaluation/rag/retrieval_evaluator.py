"""Retrieval quality evaluator for RAG system.

Measures how well the vector store retrieves relevant
historical context for pattern detection.

Metrics:
- Precision@K: Relevant docs in top K results
- Recall@K: Fraction of relevant docs retrieved
- MRR: Mean Reciprocal Rank
- NDCG: Normalized Discounted Cumulative Gain
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
import math

from .vector_store import VectorStore, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class RetrievalTestCase:
    """Test case for retrieval evaluation."""
    case_id: str
    query: str
    relevant_doc_ids: List[str]  # Ground truth relevant documents
    student_id_hash: Optional[str] = None
    description: str = ""


@dataclass
class RetrievalMetrics:
    """Metrics for retrieval quality."""
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    precision_at_5: float = 0.0
    recall_at_5: float = 0.0
    mrr: float = 0.0  # Mean Reciprocal Rank
    ndcg_at_5: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "precision_at_1": round(self.precision_at_1, 4),
            "precision_at_3": round(self.precision_at_3, 4),
            "precision_at_5": round(self.precision_at_5, 4),
            "recall_at_5": round(self.recall_at_5, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_5": round(self.ndcg_at_5, 4),
        }


@dataclass
class RetrievalTestResult:
    """Result of a single retrieval test."""
    case_id: str
    query: str
    retrieved_doc_ids: List[str]
    relevant_doc_ids: List[str]
    precision_at_k: Dict[int, float]
    recall_at_k: Dict[int, float]
    reciprocal_rank: float
    ndcg: float
    
    @property
    def first_relevant_rank(self) -> Optional[int]:
        for idx, doc_id in enumerate(self.retrieved_doc_ids):
            if doc_id in self.relevant_doc_ids:
                return idx + 1
        return None


@dataclass
class RetrievalEvaluationResult:
    """Result of full retrieval evaluation."""
    run_id: str
    started_at: datetime
    completed_at: datetime
    total_queries: int
    metrics: RetrievalMetrics
    test_results: List[RetrievalTestResult]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "total_queries": self.total_queries,
            "metrics": self.metrics.to_dict(),
        }


class RetrievalEvaluator:
    """Evaluates retrieval quality of the RAG system."""
    
    def __init__(self, vector_store: VectorStore):
        """Initialize evaluator.
        
        Args:
            vector_store: Vector store to evaluate
        """
        self.vector_store = vector_store
        
        logger.info("RETRIEVAL_EVALUATOR_INITIALIZED")
    
    def evaluate_query(
        self,
        test_case: RetrievalTestCase,
        top_k: int = 5,
    ) -> RetrievalTestResult:
        """Evaluate a single retrieval query.
        
        Args:
            test_case: Test case with query and ground truth
            top_k: Number of results to retrieve
            
        Returns:
            RetrievalTestResult with metrics
        """
        # Perform search
        results = self.vector_store.search(
            query=test_case.query,
            student_id_hash=test_case.student_id_hash,
            top_k=top_k,
        )
        
        retrieved_ids = [r.document.doc_id for r in results]
        relevant_ids = set(test_case.relevant_doc_ids)
        
        # Calculate precision@k
        precision_at_k = {}
        for k in [1, 3, 5]:
            if k <= len(retrieved_ids):
                relevant_in_k = sum(
                    1 for doc_id in retrieved_ids[:k]
                    if doc_id in relevant_ids
                )
                precision_at_k[k] = relevant_in_k / k
            else:
                precision_at_k[k] = 0.0
        
        # Calculate recall@k
        recall_at_k = {}
        for k in [1, 3, 5]:
            if len(relevant_ids) > 0:
                relevant_in_k = sum(
                    1 for doc_id in retrieved_ids[:k]
                    if doc_id in relevant_ids
                )
                recall_at_k[k] = relevant_in_k / len(relevant_ids)
            else:
                recall_at_k[k] = 1.0  # No relevant docs = perfect recall
        
        # Calculate reciprocal rank
        reciprocal_rank = 0.0
        for idx, doc_id in enumerate(retrieved_ids):
            if doc_id in relevant_ids:
                reciprocal_rank = 1.0 / (idx + 1)
                break
        
        # Calculate NDCG
        ndcg = self._calculate_ndcg(retrieved_ids, relevant_ids, top_k)
        
        return RetrievalTestResult(
            case_id=test_case.case_id,
            query=test_case.query,
            retrieved_doc_ids=retrieved_ids,
            relevant_doc_ids=test_case.relevant_doc_ids,
            precision_at_k=precision_at_k,
            recall_at_k=recall_at_k,
            reciprocal_rank=reciprocal_rank,
            ndcg=ndcg,
        )
    
    def _calculate_ndcg(
        self,
        retrieved_ids: List[str],
        relevant_ids: set,
        k: int,
    ) -> float:
        """Calculate Normalized Discounted Cumulative Gain."""
        # DCG
        dcg = 0.0
        for idx, doc_id in enumerate(retrieved_ids[:k]):
            relevance = 1.0 if doc_id in relevant_ids else 0.0
            dcg += relevance / math.log2(idx + 2)  # +2 because log2(1) = 0
        
        # Ideal DCG (all relevant docs at top)
        ideal_dcg = 0.0
        for idx in range(min(len(relevant_ids), k)):
            ideal_dcg += 1.0 / math.log2(idx + 2)
        
        if ideal_dcg == 0:
            return 0.0
        
        return dcg / ideal_dcg
    
    def evaluate_suite(
        self,
        test_cases: List[RetrievalTestCase],
    ) -> RetrievalEvaluationResult:
        """Evaluate a suite of retrieval test cases.
        
        Args:
            test_cases: List of test cases
            
        Returns:
            RetrievalEvaluationResult with aggregate metrics
        """
        run_id = f"ret_{uuid.uuid4().hex[:8]}"
        started_at = datetime.utcnow()
        
        logger.info(
            "RETRIEVAL_EVALUATION_STARTED",
            extra={"run_id": run_id, "test_count": len(test_cases)}
        )
        
        results = []
        
        # Accumulators for aggregate metrics
        sum_p1 = 0.0
        sum_p3 = 0.0
        sum_p5 = 0.0
        sum_r5 = 0.0
        sum_rr = 0.0
        sum_ndcg = 0.0
        
        for test_case in test_cases:
            result = self.evaluate_query(test_case)
            results.append(result)
            
            sum_p1 += result.precision_at_k.get(1, 0.0)
            sum_p3 += result.precision_at_k.get(3, 0.0)
            sum_p5 += result.precision_at_k.get(5, 0.0)
            sum_r5 += result.recall_at_k.get(5, 0.0)
            sum_rr += result.reciprocal_rank
            sum_ndcg += result.ndcg
        
        n = len(test_cases) if test_cases else 1
        
        metrics = RetrievalMetrics(
            precision_at_1=sum_p1 / n,
            precision_at_3=sum_p3 / n,
            precision_at_5=sum_p5 / n,
            recall_at_5=sum_r5 / n,
            mrr=sum_rr / n,
            ndcg_at_5=sum_ndcg / n,
        )
        
        completed_at = datetime.utcnow()
        
        logger.info(
            "RETRIEVAL_EVALUATION_COMPLETED",
            extra={
                "run_id": run_id,
                "total_queries": len(test_cases),
                "mrr": metrics.mrr,
                "ndcg": metrics.ndcg_at_5,
            }
        )
        
        return RetrievalEvaluationResult(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            total_queries=len(test_cases),
            metrics=metrics,
            test_results=results,
        )
    
    def generate_test_cases(
        self,
        num_cases: int = 20,
    ) -> List[RetrievalTestCase]:
        """Generate test cases from existing documents.
        
        Creates test cases by using document content as queries
        and marking the source document as relevant.
        
        Args:
            num_cases: Number of test cases to generate
            
        Returns:
            List of RetrievalTestCase
        """
        test_cases = []
        
        # Get sample of documents
        all_docs = list(self.vector_store._documents.values())
        sample_docs = all_docs[:num_cases]
        
        for idx, doc in enumerate(sample_docs):
            # Use first 100 chars of content as query
            query = doc.content[:100]
            
            # The source document should be relevant
            relevant_ids = [doc.doc_id]
            
            # Also mark documents from same student as potentially relevant
            student_hash = doc.student_id_hash
            if student_hash:
                student_docs = self.vector_store.get_student_history(student_hash)
                relevant_ids.extend([d.doc_id for d in student_docs[:3]])
            
            test_cases.append(RetrievalTestCase(
                case_id=f"RET-{idx:03d}",
                query=query,
                relevant_doc_ids=list(set(relevant_ids)),
                student_id_hash=student_hash,
                description=f"Query from doc {doc.doc_id}",
            ))
        
        return test_cases
