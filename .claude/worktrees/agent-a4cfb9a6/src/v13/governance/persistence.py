"""
Proposal Persistence Layer

Writes proposals to database in DRAFT state, handles deduplication via fingerprinting.
"""

from datetime import datetime, UTC
from typing import List, Optional, Any, Dict
from uuid import uuid4
import sqlite3

from .fingerprint import fingerprint_proposal


class ProposalPersistence:
    """
    Handles persistence of critic proposals to database.
    
    Features:
    - Automatic deduplication via fingerprinting
    - Many-to-many episode linking
    - DRAFT state initialization
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
    
    def persist_proposals(
        self,
        episode_id: str,
        critic_type: str,
        proposals: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Persist proposals from critique to database.
        
        Args:
            episode_id: Episode ID
            critic_type: Type of critic (LEAKAGE, BIAS, FEATURE, DECISION)
            proposals: List of proposal dicts with keys:
                - severity (CRITICAL, HIGH, MEDIUM, LOW)
                - finding_type (e.g., FUTURE_MARKET_LEAKAGE)
                - description (human-readable text)
                - proposed_change (dict, structured patch payload)
        
        Returns:
            List of proposal IDs (new or existing)
        """
        proposal_ids = []
        
        for proposal in proposals:
            # Generate fingerprint
            fp = fingerprint_proposal(
                critic_type=critic_type,
                finding_type=proposal["finding_type"],
                proposed_change=proposal["proposed_change"],
            )
            
            # Check if proposal already exists (any status)
            existing = self._find_by_fingerprint(fp)
            
            if existing:
                # Link existing proposal to this episode
                self._link_to_episode(existing["id"], episode_id)
                proposal_ids.append(existing["id"])
                continue
            
            # Create new proposal
            proposal_id = self._create_proposal(
                episode_id=episode_id,
                critic_type=critic_type,
                severity=proposal["severity"],
                finding_type=proposal["finding_type"],
                description=proposal["description"],
                proposed_change=proposal["proposed_change"],
                fingerprint=fp,
            )
            
            proposal_ids.append(proposal_id)
        
        self.db.commit()
        return proposal_ids
    
    def _find_by_fingerprint(self, fingerprint: str) -> Optional[Dict[str, Any]]:
        """Find existing proposal by fingerprint."""
        cursor = self.db.execute(
            "SELECT id, status FROM patch_proposals WHERE fingerprint = ?",
            (fingerprint,)
        )
        row = cursor.fetchone()
        
        if row:
            return {"id": row[0], "status": row[1]}
        return None
    
    def _create_proposal(
        self,
        episode_id: str,
        critic_type: str,
        severity: str,
        finding_type: str,
        description: str,
        proposed_change: Dict[str, Any],
        fingerprint: str,
    ) -> str:
        """Create new proposal in DRAFT state."""
        import json
        
        proposal_id = str(uuid4())
        
        self.db.execute(
            """
            INSERT INTO patch_proposals (
                id, episode_id, critic_type, severity, finding_type,
                description, proposed_change, fingerprint, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                proposal_id,
                episode_id,
                critic_type,
                severity,
                finding_type,
                description,
                json.dumps(proposed_change),
                fingerprint,
                "DRAFT",
                datetime.now(UTC).isoformat(),
            )
        )
        
        return proposal_id
    
    def _link_to_episode(self, proposal_id: str, episode_id: str):
        """Link existing proposal to new episode (many-to-many)."""
        try:
            self.db.execute(
                """
                INSERT INTO proposal_episodes (proposal_id, episode_id)
                VALUES (?, ?)
                """,
                (proposal_id, episode_id)
            )
        except sqlite3.IntegrityError:
            # Already linked, ignore
            pass
    
    def get_proposals_by_episode(
        self,
        episode_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all proposals for an episode.
        
        Args:
            episode_id: Episode ID
            status: Optional status filter (DRAFT, PENDING, ACCEPTED, REJECTED)
        
        Returns:
            List of proposal dicts
        """
        import json
        
        query = """
            SELECT id, episode_id, critic_type, severity, finding_type,
                   description, proposed_change, fingerprint, status, created_at
            FROM patch_proposals
            WHERE episode_id = ?
        """
        params = [episode_id]
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC"
        
        cursor = self.db.execute(query, params)
        rows = cursor.fetchall()
        
        proposals = []
        for row in rows:
            proposals.append({
                "id": row[0],
                "episode_id": row[1],
                "critic_type": row[2],
                "severity": row[3],
                "finding_type": row[4],
                "description": row[5],
                "proposed_change": json.loads(row[6]),
                "fingerprint": row[7],
                "status": row[8],
                "created_at": row[9],
            })
        
        return proposals
    
    def get_proposal_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Get proposal by ID."""
        import json
        
        cursor = self.db.execute(
            """
            SELECT id, episode_id, critic_type, severity, finding_type,
                   description, proposed_change, fingerprint, status, created_at,
                   reviewed_at, reviewer_id, review_rationale,
                   doctrine_version_before, doctrine_version_after
            FROM patch_proposals
            WHERE id = ?
            """,
            (proposal_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "episode_id": row[1],
            "critic_type": row[2],
            "severity": row[3],
            "finding_type": row[4],
            "description": row[5],
            "proposed_change": json.loads(row[6]),
            "fingerprint": row[7],
            "status": row[8],
            "created_at": row[9],
            "reviewed_at": row[10],
            "reviewer_id": row[11],
            "review_rationale": row[12],
            "doctrine_version_before": row[13],
            "doctrine_version_after": row[14],
        }
    
    def list_proposals(
        self,
        status: Optional[str] = None,
        critic_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        List proposals with optional filters.
        
        Args:
            status: Optional status filter
            critic_type: Optional critic type filter
            limit: Max results
            offset: Pagination offset
        
        Returns:
            List of proposal dicts
        """
        import json
        
        query = """
            SELECT id, episode_id, critic_type, severity, finding_type,
                   description, proposed_change, fingerprint, status, created_at
            FROM patch_proposals
            WHERE 1=1
        """
        params = []
        
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if critic_type:
            query += " AND critic_type = ?"
            params.append(critic_type)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cursor = self.db.execute(query, params)
        rows = cursor.fetchall()
        
        proposals = []
        for row in rows:
            proposals.append({
                "id": row[0],
                "episode_id": row[1],
                "critic_type": row[2],
                "severity": row[3],
                "finding_type": row[4],
                "description": row[5],
                "proposed_change": json.loads(row[6]),
                "fingerprint": row[7],
                "status": row[8],
                "created_at": row[9],
            })
        
        return proposals
    
    def find_similar_proposals(self, fingerprint: str) -> List[str]:
        """
        Find all episode IDs with the same proposal fingerprint.
        
        Args:
            fingerprint: Proposal fingerprint
        
        Returns:
            List of episode IDs
        """
        cursor = self.db.execute(
            """
            SELECT DISTINCT pe.episode_id
            FROM proposal_episodes pe
            WHERE pe.proposal_id IN (
                SELECT id FROM patch_proposals WHERE fingerprint = ?
            )
            """,
            (fingerprint,)
        )
        
        return [row[0] for row in cursor.fetchall()]
