"""
Proposal State Transitions — Supabase adaptation

Thin delegation layer over ProposalPersistence.
The SQLite episode_id-based transition_to_pending() is retired — the Supabase
version uses ProposalPersistence.transition_all_drafts_to_pending() instead.

State machine:
  DRAFT → PENDING → ACCEPTED / REJECTED → (ROLLED_BACK)
"""

from typing import Optional

from .persistence import ProposalPersistence


class ProposalTransitions:
    """
    Delegates all proposal state transitions to ProposalPersistence.

    Kept as a separate class so GovernanceAPI can import it without change,
    and in case richer pre/post transition hooks are needed in future.
    """

    def __init__(self, db):
        self.db = db
        self._persistence = ProposalPersistence(db)

    # ── Bulk transition (end-of-sigma-run) ────────────────────────────────────

    def transition_all_drafts_to_pending(self) -> int:
        """Transition all DRAFT proposals to PENDING. Returns count transitioned."""
        return self._persistence.transition_all_drafts_to_pending()

    # ── Individual transitions (called by GovernanceAPI after human review) ───

    def transition_to_accepted(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        doctrine_version_before: str,
        doctrine_version_after: str,
    ) -> bool:
        """Transition PENDING → ACCEPTED. Returns True on success."""
        return self._persistence.accept_proposal(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
            rationale=rationale,
            doctrine_version_before=doctrine_version_before,
            doctrine_version_after=doctrine_version_after,
        )

    def transition_to_rejected(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
    ) -> bool:
        """Transition PENDING → REJECTED. Returns True on success."""
        return self._persistence.reject_proposal(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
            rationale=rationale,
        )

    def transition_to_rolled_back(
        self,
        proposal_id: str,
        reviewer_id: str,
    ) -> bool:
        """Transition ACCEPTED → ROLLED_BACK. Returns True on success."""
        return self._persistence.rollback_proposal(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
        )

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_proposal_status(self, proposal_id: str) -> Optional[str]:
        """Return current status string for a proposal, or None if not found."""
        row = self._persistence.get_proposal_by_id(proposal_id)
        return row["status"] if row else None

    def count_by_status(self, status: str) -> int:
        """Count proposals by status."""
        rows = self._persistence.list_proposals(status=status, limit=10_000)
        return len(rows)

    def get_pending_count(self) -> int:
        """Convenience: count of PENDING proposals."""
        return self.count_by_status("PENDING")
