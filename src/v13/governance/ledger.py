"""
Governance Ledger

Immutable audit log for all governance decisions (accept, reject, rollback).
"""

from datetime import datetime, UTC
from typing import Dict, Any, Optional
from uuid import uuid4
import sqlite3
import json


class GovernanceLedger:
    """
    Writes immutable audit log entries for governance decisions.
    
    Every proposal review (accept/reject/rollback) is logged with:
    - Timestamp
    - Actor (reviewer ID)
    - Rationale
    - Doctrine version snapshot
    - Episode count at decision time
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
    
    def write_entry(
        self,
        proposal_id: str,
        action: str,  # ACCEPT, REJECT, ROLLBACK
        actor: str,
        rationale: str,
        doctrine_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Write governance decision to immutable ledger.
        
        Args:
            proposal_id: Proposal ID
            action: ACCEPT, REJECT, or ROLLBACK
            actor: Reviewer username/ID
            rationale: Human rationale for decision
            doctrine_version: Current doctrine version
            metadata: Optional additional context
        
        Returns:
            Ledger entry ID
        """
        # Get episode count at decision time
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM episodes WHERE finalized = TRUE"
        )
        episode_count = cursor.fetchone()[0]
        
        ledger_id = str(uuid4())
        
        self.db.execute(
            """
            INSERT INTO governance_ledger (
                id, proposal_id, action, actor, timestamp,
                rationale, doctrine_version_snapshot, episode_count_at_decision, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ledger_id,
                proposal_id,
                action,
                actor,
                datetime.now(UTC).isoformat(),
                rationale,
                doctrine_version,
                episode_count,
                json.dumps(metadata or {}),
            )
        )
        
        self.db.commit()
        return ledger_id
    
    def get_entries_by_proposal(self, proposal_id: str) -> list[Dict[str, Any]]:
        """Get all ledger entries for a proposal."""
        cursor = self.db.execute(
            """
            SELECT id, proposal_id, action, actor, timestamp,
                   rationale, doctrine_version_snapshot, episode_count_at_decision, metadata
            FROM governance_ledger
            WHERE proposal_id = ?
            ORDER BY timestamp DESC
            """,
            (proposal_id,)
        )
        
        entries = []
        for row in cursor.fetchall():
            entries.append({
                "id": row[0],
                "proposal_id": row[1],
                "action": row[2],
                "actor": row[3],
                "timestamp": row[4],
                "rationale": row[5],
                "doctrine_version_snapshot": row[6],
                "episode_count_at_decision": row[7],
                "metadata": json.loads(row[8]),
            })
        
        return entries
    
    def get_recent_entries(self, limit: int = 50) -> list[Dict[str, Any]]:
        """Get recent ledger entries."""
        cursor = self.db.execute(
            """
            SELECT id, proposal_id, action, actor, timestamp,
                   rationale, doctrine_version_snapshot, episode_count_at_decision, metadata
            FROM governance_ledger
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
        
        entries = []
        for row in cursor.fetchall():
            entries.append({
                "id": row[0],
                "proposal_id": row[1],
                "action": row[2],
                "actor": row[3],
                "timestamp": row[4],
                "rationale": row[5],
                "doctrine_version_snapshot": row[6],
                "episode_count_at_decision": row[7],
                "metadata": json.loads(row[8]),
            })
        
        return entries
    
    def count_by_action(self, action: str) -> int:
        """Count ledger entries by action type."""
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM governance_ledger WHERE action = ?",
            (action,)
        )
        return cursor.fetchone()[0]
    
    def get_acceptance_rate(self) -> float:
        """
        Calculate acceptance rate (accepted / (accepted + rejected)).
        
        Returns:
            Acceptance rate (0.0 to 1.0)
        """
        accepted = self.count_by_action("ACCEPT")
        rejected = self.count_by_action("REJECT")
        total = accepted + rejected
        
        if total == 0:
            return 0.0
        
        return accepted / total
