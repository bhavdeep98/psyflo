"""Audit repository for immutable audit trail storage.

Per ADR-005: QLDB or PostgreSQL with WORM enforcement.
Provides append-only storage with cryptographic verification.

In production, this integrates with:
- AWS QLDB for true immutability
- PostgreSQL with WORM policies as fallback
"""
import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from feelwell.shared.database import (
    ConnectionManager,
    RepositoryError,
)
from .audit_logger import AuditEntry, AuditAction, AuditEntity

logger = logging.getLogger(__name__)


class AuditRepository:
    """Repository for immutable audit entries.
    
    Supports both QLDB and PostgreSQL backends.
    PostgreSQL uses append-only table with no UPDATE/DELETE permissions.
    """
    
    def __init__(
        self,
        connection_manager: Optional[ConnectionManager] = None,
        qldb_ledger: Optional[str] = None,
        use_qldb: bool = False,
    ):
        """Initialize audit repository.
        
        Args:
            connection_manager: PostgreSQL connection manager
            qldb_ledger: QLDB ledger name (if using QLDB)
            use_qldb: Whether to use QLDB instead of PostgreSQL
        """
        self.connection_manager = connection_manager
        self.qldb_ledger = qldb_ledger
        self.use_qldb = use_qldb
        self._qldb_driver = None
        
        # In-memory fallback for development
        self._memory_store: List[AuditEntry] = []
        
        logger.info(
            "AUDIT_REPOSITORY_INITIALIZED",
            extra={
                "backend": "qldb" if use_qldb else "postgresql",
                "ledger": qldb_ledger,
            }
        )
    
    def _get_qldb_driver(self):
        """Get or create QLDB driver."""
        if self._qldb_driver is None and self.use_qldb:
            try:
                from pyqldb.driver.qldb_driver import QldbDriver
                self._qldb_driver = QldbDriver(ledger_name=self.qldb_ledger)
            except ImportError:
                logger.warning(
                    "QLDB_DRIVER_NOT_INSTALLED",
                    extra={"action": "falling_back_to_memory"}
                )
        return self._qldb_driver
    
    def append(self, entry: AuditEntry) -> bool:
        """Append audit entry to immutable storage.
        
        This is append-only - entries cannot be modified or deleted.
        
        Args:
            entry: AuditEntry to store
            
        Returns:
            True if stored successfully
            
        Raises:
            RepositoryError: If storage fails
        """
        if self.use_qldb:
            return self._append_qldb(entry)
        elif self.connection_manager:
            return self._append_postgres(entry)
        else:
            return self._append_memory(entry)
    
    def _append_qldb(self, entry: AuditEntry) -> bool:
        """Append to QLDB ledger."""
        driver = self._get_qldb_driver()
        if driver is None:
            return self._append_memory(entry)
        
        try:
            def insert_entry(transaction_executor):
                transaction_executor.execute_statement(
                    "INSERT INTO audit_entries ?",
                    self._entry_to_document(entry)
                )
            
            driver.execute_lambda(insert_entry)
            
            logger.info(
                "AUDIT_ENTRY_STORED_QLDB",
                extra={
                    "entry_id": entry.entry_id,
                    "action": entry.action.value,
                }
            )
            return True
            
        except Exception as e:
            logger.error(
                "QLDB_APPEND_FAILED",
                extra={"entry_id": entry.entry_id, "error": str(e)}
            )
            raise RepositoryError(f"Failed to append to QLDB: {e}")
    
    def _append_postgres(self, entry: AuditEntry) -> bool:
        """Append to PostgreSQL (append-only table)."""
        query = """
            INSERT INTO audit_entries (
                entry_id, timestamp, action, entity_type, entity_id,
                actor_id, actor_role, school_id, details,
                previous_hash, entry_hash
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        params = (
            entry.entry_id,
            entry.timestamp,
            entry.action.value,
            entry.entity_type.value,
            entry.entity_id,
            entry.actor_id,
            entry.actor_role,
            entry.school_id,
            json.dumps(entry.details),
            entry.previous_hash,
            entry.entry_hash,
        )
        
        try:
            with self.connection_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, params)
                    conn.commit()
            
            logger.info(
                "AUDIT_ENTRY_STORED_POSTGRES",
                extra={
                    "entry_id": entry.entry_id,
                    "action": entry.action.value,
                }
            )
            return True
            
        except Exception as e:
            logger.error(
                "POSTGRES_APPEND_FAILED",
                extra={"entry_id": entry.entry_id, "error": str(e)}
            )
            raise RepositoryError(f"Failed to append to PostgreSQL: {e}")
    
    def _append_memory(self, entry: AuditEntry) -> bool:
        """Append to in-memory store (development only)."""
        self._memory_store.append(entry)
        
        logger.debug(
            "AUDIT_ENTRY_STORED_MEMORY",
            extra={
                "entry_id": entry.entry_id,
                "action": entry.action.value,
            }
        )
        return True
    
    def query(
        self,
        entity_type: Optional[AuditEntity] = None,
        entity_id: Optional[str] = None,
        action: Optional[AuditAction] = None,
        actor_id: Optional[str] = None,
        school_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEntry]:
        """Query audit entries.
        
        Args:
            entity_type: Filter by entity type
            entity_id: Filter by entity ID
            action: Filter by action
            actor_id: Filter by actor
            school_id: Filter by school
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum entries to return
            
        Returns:
            List of matching AuditEntry objects
        """
        if self.use_qldb:
            return self._query_qldb(
                entity_type, entity_id, action, actor_id,
                school_id, start_date, end_date, limit
            )
        elif self.connection_manager:
            return self._query_postgres(
                entity_type, entity_id, action, actor_id,
                school_id, start_date, end_date, limit
            )
        else:
            return self._query_memory(
                entity_type, entity_id, action, actor_id,
                school_id, start_date, end_date, limit
            )
    
    def _query_postgres(
        self,
        entity_type: Optional[AuditEntity],
        entity_id: Optional[str],
        action: Optional[AuditAction],
        actor_id: Optional[str],
        school_id: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int,
    ) -> List[AuditEntry]:
        """Query PostgreSQL audit table."""
        query = "SELECT * FROM audit_entries WHERE 1=1"
        params = []
        
        if entity_type:
            query += " AND entity_type = %s"
            params.append(entity_type.value)
        if entity_id:
            query += " AND entity_id = %s"
            params.append(entity_id)
        if action:
            query += " AND action = %s"
            params.append(action.value)
        if actor_id:
            query += " AND actor_id = %s"
            params.append(actor_id)
        if school_id:
            query += " AND school_id = %s"
            params.append(school_id)
        if start_date:
            query += " AND timestamp >= %s"
            params.append(start_date)
        if end_date:
            query += " AND timestamp <= %s"
            params.append(end_date)
        
        query += " ORDER BY timestamp DESC LIMIT %s"
        params.append(limit)
        
        with self.connection_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                rows = cur.fetchall()
                
                return [self._row_to_entry(row) for row in rows]
    
    def _query_qldb(self, *args, **kwargs) -> List[AuditEntry]:
        """Query QLDB ledger."""
        # QLDB query implementation would go here
        # For now, fall back to memory
        return self._query_memory(*args, **kwargs)
    
    def _query_memory(
        self,
        entity_type: Optional[AuditEntity],
        entity_id: Optional[str],
        action: Optional[AuditAction],
        actor_id: Optional[str],
        school_id: Optional[str],
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        limit: int,
    ) -> List[AuditEntry]:
        """Query in-memory store."""
        results = self._memory_store
        
        if entity_type:
            results = [e for e in results if e.entity_type == entity_type]
        if entity_id:
            results = [e for e in results if e.entity_id == entity_id]
        if action:
            results = [e for e in results if e.action == action]
        if actor_id:
            results = [e for e in results if e.actor_id == actor_id]
        if school_id:
            results = [e for e in results if e.school_id == school_id]
        if start_date:
            results = [e for e in results if e.timestamp >= start_date]
        if end_date:
            results = [e for e in results if e.timestamp <= end_date]
        
        # Sort by timestamp descending
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)
        
        return results[:limit]
    
    def _entry_to_document(self, entry: AuditEntry) -> Dict[str, Any]:
        """Convert AuditEntry to QLDB document."""
        return {
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp.isoformat(),
            "action": entry.action.value,
            "entity_type": entry.entity_type.value,
            "entity_id": entry.entity_id,
            "actor_id": entry.actor_id,
            "actor_role": entry.actor_role,
            "school_id": entry.school_id,
            "details": entry.details,
            "previous_hash": entry.previous_hash,
            "entry_hash": entry.entry_hash,
        }
    
    def _row_to_entry(self, row: tuple) -> AuditEntry:
        """Convert PostgreSQL row to AuditEntry."""
        details = row[8]
        if isinstance(details, str):
            details = json.loads(details)
        
        return AuditEntry(
            entry_id=row[0],
            timestamp=row[1],
            action=AuditAction(row[2]),
            entity_type=AuditEntity(row[3]),
            entity_id=row[4],
            actor_id=row[5],
            actor_role=row[6],
            school_id=row[7],
            details=details or {},
            previous_hash=row[9],
            entry_hash=row[10],
        )
    
    def verify_chain(self, entries: Optional[List[AuditEntry]] = None) -> bool:
        """Verify integrity of audit chain.
        
        Args:
            entries: Entries to verify (defaults to all)
            
        Returns:
            True if chain is valid
        """
        if entries is None:
            entries = self.query(limit=10000)
        
        if not entries:
            return True
        
        # Sort by timestamp ascending for chain verification
        entries = sorted(entries, key=lambda e: e.timestamp)
        
        expected_prev = "genesis"
        for entry in entries:
            if entry.previous_hash != expected_prev:
                logger.critical(
                    "AUDIT_CHAIN_BROKEN",
                    extra={
                        "entry_id": entry.entry_id,
                        "expected": expected_prev[:16],
                        "actual": entry.previous_hash[:16],
                    }
                )
                return False
            
            computed = entry.compute_hash()
            if computed != entry.entry_hash:
                logger.critical(
                    "AUDIT_ENTRY_TAMPERED",
                    extra={
                        "entry_id": entry.entry_id,
                        "computed": computed[:16],
                        "stored": entry.entry_hash[:16],
                    }
                )
                return False
            
            expected_prev = entry.entry_hash
        
        logger.info(
            "AUDIT_CHAIN_VERIFIED",
            extra={"entry_count": len(entries)}
        )
        return True
