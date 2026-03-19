"""
Proposal Persistence Layer — Supabase adaptation

Writes proposals to patch_proposals table in DRAFT state.
Deduplicates via SHA256 fingerprint (UNIQUE constraint on fingerprint column).
source_race_id replaces the SQLite episode_id / proposal_episodes junction.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .fingerprint import fingerprint_proposal


class ProposalPersistence:
    """
    Handles persistence of proposals to Supabase patch_proposals table.

    Deduplication: fingerprint UNIQUE constraint — duplicate fingerprints
    are silently skipped. Callers check the return value (None = duplicate).
    """

    def __init__(self, db):
        self.db = db

    def persist_proposal(
        self,
        source_race_id: Optional[str],
        source_pattern_name: Optional[str],
        critic_type: str,
        severity: str,
        finding_type: str,
        description: str,
        proposed_change: Dict[str, Any],
    ) -> Optional[str]:
        """
        Persist a single proposal. Returns proposal ID if new, None if duplicate.

        Args:
            source_race_id:      Race that generated this proposal (nullable)
            source_pattern_name: learned_patterns.pattern_name that triggered this
            critic_type:         SIGMA / RPD / FEATURE / DECISION / MANUAL
            severity:            CRITICAL / HIGH / MEDIUM / LOW
            finding_type:        e.g. SIGNAL_UNDERWEIGHTED / RPD_TAG_MISS
            description:         Human-readable finding
            proposed_change:     Structured patch payload (dict)
        """
        fp = fingerprint_proposal(
            critic_type=critic_type,
            finding_type=finding_type,
            proposed_change=proposed_change,
        )
        existing = (
            self.db.table("patch_proposals")
            .select("id, status")
            .eq("fingerprint", fp)
            .execute()
        )
        if existing.data:
            return None  # duplicate — silent skip

        row = {
            "source_race_id":      source_race_id,
            "source_pattern_name": source_pattern_name,
            "critic_type":         critic_type,
            "severity":            severity,
            "finding_type":        finding_type,
            "description":         description,
            "proposed_change":     proposed_change,
            "fingerprint":         fp,
            "status":              "DRAFT",
        }
        result = self.db.table("patch_proposals").insert(row).execute()
        return result.data[0]["id"] if result.data else None

    def transition_all_drafts_to_pending(self) -> int:
        """
        Transition all DRAFT proposals to PENDING at end of a sigma run.
        Returns count transitioned.
        """
        result = (
            self.db.table("patch_proposals")
            .update({"status": "PENDING"})
            .eq("status", "DRAFT")
            .execute()
        )
        return len(result.data) if result.data else 0

    def list_proposals(
        self,
        status: Optional[str] = None,
        critic_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List proposals with optional filters, newest first."""
        q = self.db.table("patch_proposals").select("*")
        if status:
            q = q.eq("status", status)
        if critic_type:
            q = q.eq("critic_type", critic_type)
        result = q.order("created_at", desc=True).limit(limit).execute()
        return result.data or []

    def get_proposal_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """Get a proposal by UUID."""
        result = (
            self.db.table("patch_proposals")
            .select("*")
            .eq("id", proposal_id)
            .execute()
        )
        return result.data[0] if result.data else None

    def accept_proposal(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
        doctrine_version_before: str,
        doctrine_version_after: str,
    ) -> bool:
        """Transition proposal to ACCEPTED. Returns True on success."""
        result = (
            self.db.table("patch_proposals")
            .update({
                "status":                  "ACCEPTED",
                "reviewed_at":             datetime.now(timezone.utc).isoformat(),
                "reviewer_id":             reviewer_id,
                "review_rationale":        rationale,
                "doctrine_version_before": doctrine_version_before,
                "doctrine_version_after":  doctrine_version_after,
            })
            .eq("id", proposal_id)
            .eq("status", "PENDING")
            .execute()
        )
        return bool(result.data)

    def reject_proposal(
        self,
        proposal_id: str,
        reviewer_id: str,
        rationale: str,
    ) -> bool:
        """Transition proposal to REJECTED. Returns True on success."""
        result = (
            self.db.table("patch_proposals")
            .update({
                "status":           "REJECTED",
                "reviewed_at":      datetime.now(timezone.utc).isoformat(),
                "reviewer_id":      reviewer_id,
                "review_rationale": rationale,
            })
            .eq("id", proposal_id)
            .eq("status", "PENDING")
            .execute()
        )
        return bool(result.data)

    def rollback_proposal(self, proposal_id: str, reviewer_id: str) -> bool:
        """Mark a previously ACCEPTED proposal as ROLLED_BACK."""
        result = (
            self.db.table("patch_proposals")
            .update({
                "status":      "ROLLED_BACK",
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "reviewer_id": reviewer_id,
            })
            .eq("id", proposal_id)
            .eq("status", "ACCEPTED")
            .execute()
        )
        return bool(result.data)
