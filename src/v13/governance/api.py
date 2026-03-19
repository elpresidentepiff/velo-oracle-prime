"""
Governance API — Supabase adaptation

Orchestrates proposal management: list, get, accept, reject, rollback.

Hard rules:
- No automatic doctrine changes — human sign-off is mandatory for ACCEPT.
- Every decision is immutably logged to governance_ledger.
- Rollback is always available for any ACCEPTED proposal.
"""

from typing import Any, Dict, List, Optional

from .persistence import ProposalPersistence
from .transitions import ProposalTransitions
from .ledger import GovernanceLedger
from .doctrine_manager import DoctrineManager


class GovernanceAPI:
    """
    Single entry point for all governance operations.

    Usage:
        from supabase import create_client
        db = create_client(url, key)
        gov = GovernanceAPI(db)
        gov.list_proposals(status="PENDING")
        gov.accept_proposal(proposal_id, reviewer_id, rationale)
    """

    def __init__(self, db):
        self.db = db
        self.persistence = ProposalPersistence(db)
        self.transitions = ProposalTransitions(db)
        self.ledger = GovernanceLedger(db)
        self.doctrine = DoctrineManager(db)

    # ── Reads ─────────────────────────────────────────────────────────────────

    def list_proposals(
        self,
        status: Optional[str] = None,
        critic_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        List proposals with optional filters.

        Args:
            status:      DRAFT / PENDING / ACCEPTED / REJECTED / ROLLED_BACK
            critic_type: SIGMA / RPD / FEATURE / DECISION / MANUAL
            limit:       Max results (default 100)
        """
        return self.persistence.list_proposals(
            status=status,
            critic_type=critic_type,
            limit=limit,
        )

    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a proposal with its ledger history.

        Returns None if not found.
        """
        proposal = self.persistence.get_proposal_by_id(proposal_id)
        if not proposal:
            return None
        proposal["ledger_history"] = self.ledger.get_entries_by_proposal(proposal_id)
        return proposal

    def get_ledger(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Recent governance ledger entries across all proposals."""
        return self.ledger.get_recent_entries(limit=limit)

    def get_doctrine_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Doctrine version history, newest first."""
        return self.doctrine.get_version_history(limit=limit)

    def get_stats(self) -> Dict[str, Any]:
        """Governance dashboard: proposal counts, acceptance rate, active doctrine version."""
        return {
            "proposals_draft":       self.transitions.count_by_status("DRAFT"),
            "proposals_pending":     self.transitions.count_by_status("PENDING"),
            "proposals_accepted":    self.transitions.count_by_status("ACCEPTED"),
            "proposals_rejected":    self.transitions.count_by_status("REJECTED"),
            "proposals_rolled_back": self.transitions.count_by_status("ROLLED_BACK"),
            "acceptance_rate":       self.ledger.get_acceptance_rate(),
            "doctrine_version":      self.doctrine.get_active_version(),
            "doctrine_version_count": self.doctrine.count_versions(),
        }

    # ── Human-gated mutations ─────────────────────────────────────────────────

    def accept_proposal(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        change_type: str = "MINOR",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Accept a PENDING proposal and bump the doctrine version.

        Args:
            proposal_id:  UUID of the proposal
            reviewer_id:  Human reviewer ID
            rationale:    Rationale for acceptance
            change_type:  MAJOR / MINOR / PATCH (default MINOR)
            metadata:     Optional context dict

        Returns:
            {"status": "accepted", "doctrine_version": "13.1.0", "previous_version": "13.0.0"}

        Raises:
            ValueError: If proposal not found or not PENDING
        """
        proposal = self.persistence.get_proposal_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id!r} not found")
        if proposal["status"] != "PENDING":
            raise ValueError(f"Proposal is {proposal['status']!r}, not PENDING")

        current_version = self.doctrine.get_active_version()

        new_version = self.doctrine.bump_version(
            change_type=change_type,
            description=f"Accepted proposal {proposal_id}: {proposal.get('finding_type', '')}",
            created_by=reviewer_id,
        )

        self.transitions.transition_to_accepted(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
            rationale=rationale,
            doctrine_version_before=current_version,
            doctrine_version_after=new_version,
        )

        self.ledger.write_entry(
            proposal_id=proposal_id,
            action="ACCEPT",
            actor=reviewer_id,
            rationale=rationale,
            doctrine_version=new_version,
            metadata=metadata,
        )

        return {
            "status":           "accepted",
            "doctrine_version": new_version,
            "previous_version": current_version,
        }

    def reject_proposal(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Reject a PENDING proposal. Doctrine version does not change.

        Returns:
            {"status": "rejected"}

        Raises:
            ValueError: If proposal not found or not PENDING
        """
        proposal = self.persistence.get_proposal_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id!r} not found")
        if proposal["status"] != "PENDING":
            raise ValueError(f"Proposal is {proposal['status']!r}, not PENDING")

        current_version = self.doctrine.get_active_version()

        self.transitions.transition_to_rejected(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
            rationale=rationale,
        )

        self.ledger.write_entry(
            proposal_id=proposal_id,
            action="REJECT",
            actor=reviewer_id,
            rationale=rationale,
            doctrine_version=current_version,
            metadata=metadata,
        )

        return {"status": "rejected"}

    def rollback_proposal(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Roll back a previously ACCEPTED proposal.

        Does NOT revert the doctrine version bump — that requires a separate
        doctrine rollback decision.

        Returns:
            {"status": "rolled_back"}

        Raises:
            ValueError: If proposal not found or not ACCEPTED
        """
        proposal = self.persistence.get_proposal_by_id(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id!r} not found")
        if proposal["status"] != "ACCEPTED":
            raise ValueError(f"Proposal is {proposal['status']!r}, not ACCEPTED")

        current_version = self.doctrine.get_active_version()

        self.transitions.transition_to_rolled_back(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
        )

        self.ledger.write_entry(
            proposal_id=proposal_id,
            action="ROLLBACK",
            actor=reviewer_id,
            rationale=rationale,
            doctrine_version=current_version,
            metadata=metadata,
        )

        return {"status": "rolled_back"}
