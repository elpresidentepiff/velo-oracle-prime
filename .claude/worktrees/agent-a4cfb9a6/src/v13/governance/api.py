"""
Governance API

Minimal REST API for proposal management (list, get, accept, reject).

No UI, no auto-apply, no doctrine mutation without explicit human action.
"""

from typing import Optional, List, Dict, Any
import sqlite3

from .persistence import ProposalPersistence
from .transitions import ProposalTransitions
from .ledger import GovernanceLedger
from .doctrine_manager import DoctrineManager


class GovernanceAPI:
    """
    Governance API for proposal management.
    
    Endpoints:
    - list_proposals: List proposals with optional filters
    - get_proposal: Get proposal details
    - accept_proposal: Accept proposal and bump doctrine version
    - reject_proposal: Reject proposal
    - get_ledger: Get governance ledger entries
    - get_doctrine_versions: Get doctrine version history
    """
    
    def __init__(self, db_connection: sqlite3.Connection):
        self.db = db_connection
        self.persistence = ProposalPersistence(db_connection)
        self.transitions = ProposalTransitions(db_connection)
        self.ledger = GovernanceLedger(db_connection)
        self.doctrine = DoctrineManager(db_connection)
    
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
            status: Optional status filter (DRAFT, PENDING, ACCEPTED, REJECTED)
            critic_type: Optional critic type filter (LEAKAGE, BIAS, FEATURE, DECISION)
            limit: Max results (default 100)
            offset: Pagination offset (default 0)
        
        Returns:
            List of proposal dicts
        """
        return self.persistence.list_proposals(
            status=status,
            critic_type=critic_type,
            limit=limit,
            offset=offset
        )
    
    def get_proposal(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get proposal details.
        
        Args:
            proposal_id: Proposal ID
        
        Returns:
            Proposal dict or None if not found
        """
        proposal = self.persistence.get_proposal_by_id(proposal_id)
        
        if not proposal:
            return None
        
        # Add similar proposals (same fingerprint)
        similar = self.persistence.find_similar_proposals(proposal["fingerprint"])
        proposal["similar_episodes"] = similar
        
        # Add ledger history
        proposal["ledger_history"] = self.ledger.get_entries_by_proposal(proposal_id)
        
        return proposal
    
    def accept_proposal(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Accept a proposal and bump doctrine version.
        
        Args:
            proposal_id: Proposal ID
            reviewer_id: Reviewer username/ID
            rationale: Human rationale for acceptance
            metadata: Optional additional context
        
        Returns:
            Dict with status and new doctrine version
        
        Raises:
            ValueError: If proposal not found or not PENDING
        """
        # Verify proposal exists and is PENDING
        proposal = self.persistence.get_proposal_by_id(proposal_id)
        
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        
        if proposal["status"] != "PENDING":
            raise ValueError(f"Proposal is {proposal['status']}, not PENDING")
        
        # Get current doctrine version
        current_version = self.doctrine.get_active_version()
        
        # Bump doctrine version (no actual rule application yet)
        new_version = self.doctrine.bump_version(
            change_type="MINOR",  # New rule added
            description=f"Accepted proposal {proposal_id}: {proposal['finding_type']}",
            created_by=reviewer_id,
        )
        
        # Transition proposal to ACCEPTED
        self.transitions.transition_to_accepted(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
            rationale=rationale,
            doctrine_version_after=new_version,
        )
        
        # Write ledger entry
        self.ledger.write_entry(
            proposal_id=proposal_id,
            action="ACCEPT",
            actor=reviewer_id,
            rationale=rationale,
            doctrine_version=new_version,
            metadata=metadata,
        )
        
        return {
            "status": "accepted",
            "doctrine_version": new_version,
            "previous_version": current_version,
        }
    
    def reject_proposal(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Reject a proposal.
        
        Args:
            proposal_id: Proposal ID
            reviewer_id: Reviewer username/ID
            rationale: Human rationale for rejection
            metadata: Optional additional context
        
        Returns:
            Dict with status
        
        Raises:
            ValueError: If proposal not found or not PENDING
        """
        # Verify proposal exists and is PENDING
        proposal = self.persistence.get_proposal_by_id(proposal_id)
        
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")
        
        if proposal["status"] != "PENDING":
            raise ValueError(f"Proposal is {proposal['status']}, not PENDING")
        
        # Get current doctrine version
        current_version = self.doctrine.get_active_version()
        
        # Transition proposal to REJECTED
        self.transitions.transition_to_rejected(
            proposal_id=proposal_id,
            reviewer_id=reviewer_id,
            rationale=rationale,
        )
        
        # Write ledger entry
        self.ledger.write_entry(
            proposal_id=proposal_id,
            action="REJECT",
            actor=reviewer_id,
            rationale=rationale,
            doctrine_version=current_version,
            metadata=metadata,
        )
        
        return {"status": "rejected"}
    
    def get_ledger(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent governance ledger entries.
        
        Args:
            limit: Max results (default 50)
        
        Returns:
            List of ledger entry dicts
        """
        return self.ledger.get_recent_entries(limit=limit)
    
    def get_doctrine_versions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get doctrine version history.
        
        Args:
            limit: Max results (default 50)
        
        Returns:
            List of version dicts
        """
        return self.doctrine.get_version_history(limit=limit)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get governance statistics.
        
        Returns:
            Dict with proposal counts, acceptance rate, doctrine version
        """
        return {
            "proposals_draft": self.transitions.count_by_status("DRAFT"),
            "proposals_pending": self.transitions.count_by_status("PENDING"),
            "proposals_accepted": self.transitions.count_by_status("ACCEPTED"),
            "proposals_rejected": self.transitions.count_by_status("REJECTED"),
            "acceptance_rate": self.ledger.get_acceptance_rate(),
            "doctrine_version": self.doctrine.get_active_version(),
            "doctrine_version_count": self.doctrine.count_versions(),
        }
