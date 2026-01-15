"""Vector store for RAG-based historical context retrieval.

Stores session summaries and enables semantic search for
pattern detection across student history.

Per ADR-003: All stored data uses hashed student IDs.
Per ADR-005: All access operations emit audit events.
"""
import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Document stored in vector store."""
    doc_id: str
    content: str
    embedding: List[float]
    metadata: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def student_id_hash(self) -> Optional[str]:
        return self.metadata.get("student_id_hash")
    
    @property
    def session_id(self) -> Optional[str]:
        return self.metadata.get("session_id")
    
    @property
    def risk_score(self) -> float:
        return self.metadata.get("risk_score", 0.0)


@dataclass
class SearchResult:
    """Result from vector search."""
    document: Document
    similarity_score: float
    rank: int


class VectorStore:
    """In-memory vector store for evaluation.
    
    Production would use Pinecone, Weaviate, or pgvector.
    This implementation uses cosine similarity for testing.
    """
    
    def __init__(self, embedding_dim: int = 384):
        """Initialize vector store.
        
        Args:
            embedding_dim: Dimension of embedding vectors
        """
        self.embedding_dim = embedding_dim
        self._documents: Dict[str, Document] = {}
        self._student_index: Dict[str, List[str]] = {}  # student_hash -> doc_ids
        
        logger.info(
            "VECTOR_STORE_INITIALIZED",
            extra={"embedding_dim": embedding_dim}
        )
    
    def add_document(
        self,
        content: str,
        metadata: Dict[str, Any],
        embedding: Optional[List[float]] = None,
    ) -> Document:
        """Add a document to the store.
        
        Args:
            content: Text content of document
            metadata: Document metadata (must include student_id_hash)
            embedding: Pre-computed embedding (or will be generated)
            
        Returns:
            Created Document
        """
        doc_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # Generate simple embedding if not provided
        if embedding is None:
            embedding = self._generate_embedding(content)
        
        doc = Document(
            doc_id=doc_id,
            content=content,
            embedding=embedding,
            metadata=metadata,
        )
        
        self._documents[doc_id] = doc
        
        # Index by student
        student_hash = metadata.get("student_id_hash")
        if student_hash:
            if student_hash not in self._student_index:
                self._student_index[student_hash] = []
            self._student_index[student_hash].append(doc_id)
        
        logger.info(
            "DOCUMENT_ADDED",
            extra={
                "doc_id": doc_id,
                "student_id_hash": student_hash,
                "content_length": len(content),
            }
        )
        
        return doc
    
    def search(
        self,
        query: str,
        student_id_hash: Optional[str] = None,
        top_k: int = 5,
        min_similarity: float = 0.0,
    ) -> List[SearchResult]:
        """Search for similar documents.
        
        Args:
            query: Search query text
            student_id_hash: Filter to specific student
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of SearchResult ordered by similarity
        """
        query_embedding = self._generate_embedding(query)
        
        # Get candidate documents
        if student_id_hash:
            doc_ids = self._student_index.get(student_id_hash, [])
            candidates = [self._documents[did] for did in doc_ids if did in self._documents]
        else:
            candidates = list(self._documents.values())
        
        # Calculate similarities
        results = []
        for doc in candidates:
            similarity = self._cosine_similarity(query_embedding, doc.embedding)
            if similarity >= min_similarity:
                results.append((doc, similarity))
        
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Return top_k
        search_results = [
            SearchResult(document=doc, similarity_score=sim, rank=idx + 1)
            for idx, (doc, sim) in enumerate(results[:top_k])
        ]
        
        logger.info(
            "VECTOR_SEARCH_COMPLETED",
            extra={
                "query_length": len(query),
                "student_filter": student_id_hash is not None,
                "candidates": len(candidates),
                "results": len(search_results),
            }
        )
        
        return search_results
    
    def get_student_history(
        self,
        student_id_hash: str,
        limit: int = 100,
    ) -> List[Document]:
        """Get all documents for a student.
        
        Args:
            student_id_hash: Hashed student identifier
            limit: Maximum documents to return
            
        Returns:
            List of documents sorted by creation time
        """
        doc_ids = self._student_index.get(student_id_hash, [])
        docs = [self._documents[did] for did in doc_ids if did in self._documents]
        
        # Sort by creation time
        docs.sort(key=lambda d: d.created_at)
        
        return docs[:limit]
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate simple embedding for text.
        
        Production would use sentence-transformers or similar.
        This uses a hash-based approach for testing.
        """
        # Simple hash-based embedding for testing
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # Convert hash to float vector
        embedding = []
        for i in range(0, min(len(text_hash), self.embedding_dim * 2), 2):
            byte_val = int(text_hash[i:i+2], 16)
            embedding.append((byte_val - 128) / 128.0)
        
        # Pad or truncate to embedding_dim
        while len(embedding) < self.embedding_dim:
            embedding.append(0.0)
        
        return embedding[:self.embedding_dim]
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def clear(self) -> None:
        """Clear all documents from store."""
        self._documents.clear()
        self._student_index.clear()
        logger.info("VECTOR_STORE_CLEARED")
    
    @property
    def document_count(self) -> int:
        return len(self._documents)
    
    @property
    def student_count(self) -> int:
        return len(self._student_index)
