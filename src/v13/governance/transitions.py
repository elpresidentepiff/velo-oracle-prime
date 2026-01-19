"""
Proposal State Transitions

Manages proposal lifecycle state machine:
DRAFT → PENDING → ACCEPTED/REJECTED → (ROLLED_BACK)

Key transition: DRAFT → PENDING occurs when episode is finalized.
"""

from datetime import datetime, UTC
import sqlite3


class ProposalTransitions:
    """
    Handles proposal state transitions.
    
    State machine:
    - DRAFT: Critic emitted, not ready for review
    - PENDING: Episode finalized, ready for human review
    - ACCEPTED: Human approved, doctrine updated
    - REJECTED: Human declined, archived
    - ROLLED_BACK: Previously accepted, now reverted
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
    
    def transition_to_pending(self, episode_id: str):
        """
        Transition all DRAFT proposals for an episode to PENDING.
        
        Called when episode is finalized (outcome recorded).
        
        Args:
            episode_id: Episode ID
        """
        # Transition direct proposals (episode_id column)
        self.db.execute(
            """
            UPDATE patch_proposals
            SET status = 'PENDING'
            WHERE episode_id = ? AND status = 'DRAFT'
            """,
            (episode_id,)
        )
        
        # Transition linked proposals (via proposal_episodes junction)
        self.db.execute(
            """
            UPDATE patch_proposals
            SET status = 'PENDING'
            WHERE id IN (
                SELECT proposal_id FROM proposal_episodes WHERE episode_id = ?
            ) AND status = 'DRAFT'
            """,
            (episode_id,)
        )
        
        self.db.commit()
    
    def transition_to_accepted(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        doctrine_version_after: str
    ):
        """
        Transition proposal to ACCEPTED.
        
        Args:
            proposal_id: Proposal ID
            reviewer_id: Reviewer username/ID
            rationale: Human rationale for acceptance
            doctrine_version_after: New doctrine version
        """
        self.db.execute(
            """
            UPDATE patch_proposals
            SET status = 'ACCEPTED',
                reviewed_at = ?,
                reviewer_id = ?,
                review_rationale = ?,
                doctrine_version_after = ?
            WHERE id = ? AND status = 'PENDING'
            """,
            (
                datetime.now(UTC).isoformat(),
                reviewer_id,
                rationale,
                doctrine_version_after,
                proposal_id,
            )
        )
        
        if self.db.total_changes == 0:
            raise ValueError(f"Proposal {proposal_id} not found or not PENDING")
        
        self.db.commit()
    
    def transition_to_rejected(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str
    ):
        """
        Transition proposal to REJECTED.
        
        Args:
            proposal_id: Proposal ID
            reviewer_id: Reviewer username/ID
            rationale: Human rationale for rejection
        """
        self.db.execute(
            """
            UPDATE patch_proposals
            SET status = 'REJECTED',
                reviewed_at = ?,
                reviewer_id = ?,
                review_rationale = ?
            WHERE id = ? AND status = 'PENDING'
            """,
            (
                datetime.now(UTC).isoformat(),
                reviewer_id,
                rationale,
                proposal_id,
            )
        )
        
        if self.db.total_changes == 0:
            raise ValueError(f"Proposal {proposal_id} not found or not PENDING")
        
        self.db.commit()
    
    def transition_to_rolled_back(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str
    ):
        """
        Transition proposal to ROLLED_BACK.
        
        Args:
            proposal_id: Proposal ID
            reviewer_id: Reviewer username/ID
            rationale: Human rationale for rollback
        """
        self.db.execute(
            """
            UPDATE patch_proposals
            SET status = 'ROLLED_BACK'
            WHERE id = ? AND status = 'ACCEPTED'
            """,
            (proposal_id,)
        )
        
        if self.db.total_changes == 0:
            raise ValueError(f"Proposal {proposal_id} not found or not ACCEPTED")
        
        self.db.commit()
    
    def get_proposal_status(self, proposal_id: str) -> str:
        """Get current status of a proposal."""
        cursor = self.db.execute(
            "SELECT status FROM patch_proposals WHERE id = ?",
            (proposal_id,)
        )
        row = cursor.fetchone()
        
        if not row:
            raise ValueError(f"Proposal {proposal_id} not found")
        
        return row[0]
    
    def count_by_status(self, status: str) -> int:
        """Count proposals by status."""
        cursor = self.db.execute(
            "SELECT COUNT(*) FROM patch_proposals WHERE status = ?",
            (status,)
        )
        return cursor.fetchone()[0]
    
    def get_pending_count(self) -> int:
        """Get count of pending proposals (convenience method)."""
        return self.count_by_status("PENDING")
