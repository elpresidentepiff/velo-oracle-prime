"""
VÉLØ — Apply Approved Proposals to Runtime Overrides
=====================================================
Reads patch_proposals with status=ACCEPTED and translates relevant ones
into runtime_overrides rows (upsert).

Architecture (immutable):
  learned_patterns  = observations
  patch_proposals   = candidate changes
  runtime_overrides = live scoring config  ← THIS SCRIPT WRITES HERE

What this script does NOT do:
  - Does NOT edit source code
  - Does NOT modify hardcoded constants
  - Does NOT alter .pkl model weights
  - Does NOT read learned_patterns directly (only approved proposals)

Supported proposal finding_types (v1):
  TIER_THRESHOLD_ADJUSTMENT  → updates tier_thresholds.value_json and activates it
  PROMOTION_BLOCKER_RULE     → adds/updates blockers in tier_promotion_blockers
  TRAP_ESCALATION_RULE       → adds/updates rules in trap_escalation_rules

Run:
  python scripts/apply_approved_proposals.py [--dry-run] [--verbose]

Flags:
  --dry-run   Show what would be written without writing anything
  --verbose   Print full proposal payload for each applied change

After running:
  Scoring on the next run_prime_today.py call will read the new overrides.
  Verify with: python scripts/run_velo_daily.py --verify-only
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from supabase import create_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("velo.apply_proposals")

LEGACY_SCRIPT_STATUS = "QUARANTINED_WAVE_1"
LEGACY_SCRIPT_OWNER = "TBD"
LEGACY_EXECUTION_ENV = "VELO_LEGACY_ALLOW_APPLY_APPROVED_PROPOSALS"
SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY", ""))


def _require_legacy_override() -> None:
    if os.getenv(LEGACY_EXECUTION_ENV) == "1":
        return
    raise SystemExit(
        "Legacy script is quarantined and blocked by default. "
        f"Set {LEGACY_EXECUTION_ENV}=1 for an intentional run."
    )

# Only these finding_types are actioned — all others are ignored (logged)
_SUPPORTED_TYPES = {
    "TIER_THRESHOLD_ADJUSTMENT",
    "PROMOTION_BLOCKER_RULE",
    "TRAP_ESCALATION_RULE",
}

# Tier ordering — used to validate max_tier values
_VALID_TIERS = {"A", "B", "C", "D", "X"}


def _load_approved_proposals(db) -> list[dict]:
    """Return all patch_proposals with status=ACCEPTED (approved for actuation).

    The patch_proposals lifecycle is:
      DRAFT → PENDING (sigma run) → ACCEPTED (human review) → [applied here]

    This script processes all ACCEPTED proposals of supported types that have
    not yet been translated into a runtime_overrides row.
    """
    rows = (
        db.table("patch_proposals")
        .select("id, finding_type, severity, description, proposed_change, "
                "source_pattern_name, created_at")
        .eq("status", "ACCEPTED")
        .order("created_at")
        .execute()
    )
    return rows.data or []


def _get_current_override(db, key: str) -> dict | None:
    """Fetch current runtime_overrides row for a key. Returns None if absent."""
    rows = (
        db.table("runtime_overrides")
        .select("id, override_key, value_json, status")
        .eq("override_key", key)
        .execute()
    )
    if rows.data:
        return rows.data[0]
    return None


def _upsert_override(db, key: str, value_json: dict, source: str,
                     notes: str, dry_run: bool) -> bool:
    """Upsert a runtime_overrides row and set status=ACTIVE."""
    now = datetime.now(timezone.utc).isoformat()
    row = {
        "override_key": key,
        "scope":        "global",
        "value_json":   value_json,
        "status":       "ACTIVE",
        "source":       source,
        "effective_from": now,
        "effective_to": None,
        "updated_at":   now,
        "notes":        notes[:500] if notes else None,
    }
    if dry_run:
        log.info("[DRY-RUN] Would upsert runtime_overrides[%s] = %s",
                 key, json.dumps(value_json, indent=2))
        return True
    try:
        db.table("runtime_overrides").upsert(
            row, on_conflict="override_key"
        ).execute()
        log.info("  Upserted runtime_overrides[%s] → ACTIVE", key)
        return True
    except Exception as e:
        log.error("  Upsert failed for key=%s: %s", key, e)
        return False


def _mark_proposal_applied(db, proposal_id: str, dry_run: bool) -> None:
    """
    Proposal is already ACCEPTED — log actuation without changing status.
    Status stays ACCEPTED as the terminal approval state.
    The runtime_override row created/updated is the actuation record.
    """
    if dry_run:
        log.info("[DRY-RUN] Would actuate proposal %s (status stays ACCEPTED)", proposal_id)
        return
    log.info("  Proposal %s actuated → runtime_override written (status: ACCEPTED)", proposal_id)


# ── Proposal type handlers ─────────────────────────────────────────────────────

def _apply_tier_threshold_adjustment(db, proposal: dict, dry_run: bool, verbose: bool) -> bool:
    """
    TIER_THRESHOLD_ADJUSTMENT → update tier_thresholds.value_json and activate.

    Reads current tier_thresholds value, applies the proposed delta to the
    specified tier/field, then writes back as ACTIVE.
    """
    change = proposal.get("proposed_change") or {}
    tier   = change.get("tier")
    field  = change.get("field")
    proposed_val = change.get("proposed")

    if not all([tier, field, proposed_val is not None]):
        log.warning("  TIER_THRESHOLD_ADJUSTMENT: missing tier/field/proposed in proposed_change")
        return False

    if tier not in _VALID_TIERS:
        log.warning("  TIER_THRESHOLD_ADJUSTMENT: invalid tier '%s'", tier)
        return False

    # Load current value_json (or seed defaults)
    current_row = _get_current_override(db, "tier_thresholds")
    if current_row:
        current_val = current_row.get("value_json") or {}
        if isinstance(current_val, str):
            current_val = json.loads(current_val)
    else:
        # Seed from hardcoded baseline
        current_val = {
            "A": {"min_prob": 0.32, "min_gap": 0.08, "min_place": 0.52},
            "B": {"min_prob": 0.15, "min_gap": 0.03, "min_place": 0.45, "min_improve": 0.18},
            "C": {"min_prob": 0.13, "min_gap": 0.02, "rescue_place": 0.55, "rescue_prob": 0.11},
            "X": {"flat_field_prob_max": 0.10, "max_gap": 0.015, "max_place": 0.40},
        }

    if tier not in current_val:
        current_val[tier] = {}

    prev = current_val[tier].get(field, "(absent)")
    current_val[tier][field] = proposed_val

    if verbose:
        log.info("  %s.%s: %s → %s", tier, field, prev, proposed_val)

    notes = (
        f"Applied TIER_THRESHOLD_ADJUSTMENT: {tier}.{field} {prev}→{proposed_val} | "
        f"proposal={proposal['id']} pattern={proposal.get('source_pattern_name')} | "
        f"{proposal.get('description', '')[:200]}"
    )

    return _upsert_override(
        db, "tier_thresholds", current_val,
        source="APPROVED_PROPOSAL", notes=notes, dry_run=dry_run
    )


def _apply_promotion_blocker_rule(db, proposal: dict, dry_run: bool, verbose: bool) -> bool:
    """
    PROMOTION_BLOCKER_RULE → add blocker to tier_promotion_blockers and activate.

    Appends new blocker if not already present (deduped by 'when' conditions).
    """
    change = proposal.get("proposed_change") or {}
    new_blocker = change.get("blocker")

    if not new_blocker or not isinstance(new_blocker, dict):
        log.warning("  PROMOTION_BLOCKER_RULE: missing 'blocker' in proposed_change")
        return False

    if "when" not in new_blocker or "max_tier" not in new_blocker:
        log.warning("  PROMOTION_BLOCKER_RULE: blocker must have 'when' and 'max_tier'")
        return False

    if new_blocker["max_tier"] not in _VALID_TIERS:
        log.warning("  PROMOTION_BLOCKER_RULE: invalid max_tier '%s'", new_blocker["max_tier"])
        return False

    current_row = _get_current_override(db, "tier_promotion_blockers")
    if current_row:
        current_val = current_row.get("value_json") or {}
        if isinstance(current_val, str):
            current_val = json.loads(current_val)
    else:
        current_val = {"blockers": []}

    blockers = current_val.get("blockers", [])

    # Deduplicate by 'when' conditions (don't add duplicate blockers)
    new_when = json.dumps(new_blocker["when"], sort_keys=True)
    existing_whens = [json.dumps(b.get("when", {}), sort_keys=True) for b in blockers]

    if new_when not in existing_whens:
        blockers.append(new_blocker)
        current_val["blockers"] = blockers
    else:
        log.info("  PROMOTION_BLOCKER_RULE: blocker already present for when=%s — activating if inactive",
                 new_blocker["when"])
        # Blocker already in value_json but override may be INACTIVE — still activate

    current_val["blockers"] = blockers

    if verbose:
        log.info("  Adding blocker: when=%s max_tier=%s",
                 new_blocker["when"], new_blocker["max_tier"])

    notes = (
        f"Applied PROMOTION_BLOCKER_RULE: added blocker {new_blocker['when']} → "
        f"max_tier={new_blocker['max_tier']} | "
        f"proposal={proposal['id']} pattern={proposal.get('source_pattern_name')}"
    )

    return _upsert_override(
        db, "tier_promotion_blockers", current_val,
        source="APPROVED_PROPOSAL", notes=notes, dry_run=dry_run
    )


def _apply_trap_escalation_rule(db, proposal: dict, dry_run: bool, verbose: bool) -> bool:
    """
    TRAP_ESCALATION_RULE → add rule to trap_escalation_rules and activate.
    """
    change = proposal.get("proposed_change") or {}
    new_rule = change.get("rule")

    if not new_rule or not isinstance(new_rule, dict):
        log.warning("  TRAP_ESCALATION_RULE: missing 'rule' in proposed_change")
        return False

    if "when" not in new_rule or "action" not in new_rule:
        log.warning("  TRAP_ESCALATION_RULE: rule must have 'when' and 'action'")
        return False

    current_row = _get_current_override(db, "trap_escalation_rules")
    if current_row:
        current_val = current_row.get("value_json") or {}
        if isinstance(current_val, str):
            current_val = json.loads(current_val)
    else:
        current_val = {"rules": []}

    rules = current_val.get("rules", [])

    # Deduplicate by 'when' + 'action'
    new_key = json.dumps({"when": new_rule["when"], "action": new_rule["action"]}, sort_keys=True)
    existing_keys = [
        json.dumps({"when": r.get("when", {}), "action": r.get("action", "")}, sort_keys=True)
        for r in rules
    ]

    if new_key in existing_keys:
        log.info("  TRAP_ESCALATION_RULE: rule already present — skipping")
        return True

    rules.append(new_rule)
    current_val["rules"] = rules

    if verbose:
        log.info("  Adding trap rule: when=%s action=%s", new_rule["when"], new_rule["action"])

    notes = (
        f"Applied TRAP_ESCALATION_RULE: {new_rule['when']} → {new_rule['action']} | "
        f"proposal={proposal['id']} pattern={proposal.get('source_pattern_name')}"
    )

    return _upsert_override(
        db, "trap_escalation_rules", current_val,
        source="APPROVED_PROPOSAL", notes=notes, dry_run=dry_run
    )


# ── Dispatch table ─────────────────────────────────────────────────────────────

_HANDLERS = {
    "TIER_THRESHOLD_ADJUSTMENT": _apply_tier_threshold_adjustment,
    "PROMOTION_BLOCKER_RULE":    _apply_promotion_blocker_rule,
    "TRAP_ESCALATION_RULE":      _apply_trap_escalation_rule,
}


def main():
    parser = argparse.ArgumentParser(description="Apply APPROVED proposals to runtime_overrides")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would change without writing")
    parser.add_argument("--verbose", action="store_true",
                        help="Print full proposal details")
    args = parser.parse_args()

    if not SUPA_URL or not SUPA_KEY:
        log.error("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set in .env")
        sys.exit(1)

    db = create_client(SUPA_URL, SUPA_KEY)

    print(f"\nVÉLØ APPLY APPROVED PROPOSALS{' [DRY-RUN]' if args.dry_run else ''}")
    print(f"{'='*60}")
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S UTC')}")

    proposals = _load_approved_proposals(db)
    print(f"\nFound {len(proposals)} ACCEPTED proposals (ready for actuation)")

    if not proposals:
        print("Nothing to apply.")
        return

    applied = 0
    skipped = 0
    failed  = 0

    for p in proposals:
        pid   = p["id"]
        ftype = p.get("finding_type", "")
        desc  = p.get("description", "")[:80]
        pat   = p.get("source_pattern_name", "?")
        sev   = p.get("severity", "?")

        print(f"\n  [{ftype}] {sev} | pattern={pat}")
        print(f"  desc: {desc}")

        if args.verbose:
            print(f"  payload: {json.dumps(p.get('proposed_change'), indent=4)}")

        if ftype not in _SUPPORTED_TYPES:
            log.info("  Skipping unsupported finding_type: %s", ftype)
            skipped += 1
            continue

        handler = _HANDLERS.get(ftype)
        if not handler:
            log.warning("  No handler registered for %s — skipping", ftype)
            skipped += 1
            continue

        ok = handler(db, p, dry_run=args.dry_run, verbose=args.verbose)
        if ok:
            if not args.dry_run:
                _mark_proposal_applied(db, pid, dry_run=False)
            applied += 1
            print(f"  STATUS: {'[DRY-RUN] would apply' if args.dry_run else 'APPLIED → ACCEPTED'}")
        else:
            failed += 1
            print(f"  STATUS: FAILED")

    print(f"\n{'='*60}")
    print(f"Results: {applied} applied, {skipped} skipped, {failed} failed")
    if args.dry_run:
        print("DRY-RUN: no changes written to Supabase")
    else:
        print("Runtime overrides updated. Next run_prime_today.py will load them.")

    # Print current active overrides
    active = (
        db.table("runtime_overrides")
        .select("override_key, status, source, updated_at, notes")
        .eq("status", "ACTIVE")
        .execute()
    )
    active_rows = active.data or []
    if active_rows:
        print(f"\nACTIVE runtime_overrides ({len(active_rows)}):")
        for r in active_rows:
            print(f"  {r['override_key']:35s} source={r['source']} updated={r['updated_at'][:19]}")
    else:
        print("\nNo ACTIVE runtime_overrides (hardcoded thresholds will apply)")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    _require_legacy_override()
    main()
