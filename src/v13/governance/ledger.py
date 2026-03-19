"""
Governance Ledger — Supabase adaptation

Immutable audit log for all governance decisions (accept, reject, rollback).
Writes to the governance_ledger table. Rows are never deleted or updated.

episode_count_at_decision: sourced from sigma_audits row count (proxy for
observations in the system at decision time).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class GovernanceLedger:
    """
    Append-only audit log for governance decisions.

    Every proposal review (accept/reject/rollback) produces one ledger row.
    Ledger rows are immutable by convention — no UPDATE or DELETE is issued.
    """

    def __init__(self, db):
        self.db = db

    # ── Writes ────────────────────────────────────────────────────────────────

    def write_entry(
        self,
        proposal_id: str,
        action: str,
        actor: str,
        rationale: str,
        doctrine_version: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Write one immutable governance decision entry to the ledger.

        Args:
            proposal_id:      UUID of the proposal being reviewed
            action:           ACCEPT / REJECT / ROLLBACK
            actor:            Reviewer ID
            rationale:        Human rationale for the decision
            doctrine_version: Active doctrine version at decision time
            metadata:         Optional additional context

        Returns:
            ID of the new ledger row (UUID string)
        """
        # Observation count: sigma_audits rows at decision time
        try:
            audit_result = self.db.table("sigma_audits").select("id").execute()
            observation_count = len(audit_result.data) if audit_result.data else 0
        except Exception:
            observation_count = 0

        row = {
            "proposal_id":                proposal_id,
            "action":                     action,
            "actor":                      actor,
            "timestamp":                  datetime.now(timezone.utc).isoformat(),
            "rationale":                  rationale,
            "doctrine_version_snapshot":  doctrine_version,
            "episode_count_at_decision":  observation_count,
            "metadata":                   metadata or {},
        }
        result = self.db.table("governance_ledger").insert(row).execute()
        return result.data[0]["id"] if result.data else ""

    # ── Reads ─────────────────────────────────────────────────────────────────

    def get_entries_by_proposal(self, proposal_id: str) -> List[Dict[str, Any]]:
        """All ledger entries for a proposal, newest first."""
        result = (
            self.db.table("governance_ledger")
            .select("*")
            .eq("proposal_id", proposal_id)
            .order("timestamp", desc=True)
            .execute()
        )
        return result.data or []

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Recent ledger entries across all proposals, newest first."""
        result = (
            self.db.table("governance_ledger")
            .select("*")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []

    def count_by_action(self, action: str) -> int:
        """Count ledger rows for a specific action type."""
        result = (
            self.db.table("governance_ledger")
            .select("id")
            .eq("action", action)
            .execute()
        )
        return len(result.data) if result.data else 0

    def get_acceptance_rate(self) -> float:
        """Acceptance rate = accepted / (accepted + rejected). 0.0 if no decisions."""
        accepted = self.count_by_action("ACCEPT")
        rejected = self.count_by_action("REJECT")
        total = accepted + rejected
        return round(accepted / total, 4) if total else 0.0
