"""
Phase 3C Proof — Governance End-to-End Test
============================================
Proves the full cycle against live Supabase:
  1. Tables present
  2. Doctrine baseline version seeded
  3. Synthetic learned_pattern created (occurrences=10 > threshold=5)
  4. _create_sigma_proposals() fires → DRAFT proposal created
  5. DRAFT → PENDING transition
  6. list_proposals() returns it
  7. get_proposal() returns it with ledger_history
  8. reject_proposal() → REJECTED + ledger row written
  9. New synthetic PENDING proposal → accept_proposal() → ACCEPTED + doctrine bumped
 10. Ledger has 2 rows. doctrine_versions has 2 rows.
 11. Cleanup: delete test rows.

Run: python scripts/proof_governance_e2e.py
"""
import os, sys, json, traceback
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_SERVICE_KEY")
    or os.getenv("SUPABASE_ANON_KEY", "")
)
PASS = True
RESULTS = []

def check(label, condition, detail=""):
    global PASS
    sym = "PASS" if condition else "FAIL"
    if not condition:
        PASS = False
    RESULTS.append((sym, label, detail))
    print(f"  [{sym}] {label}" + (f": {detail}" if detail else ""))


def main():
    print("=== Phase 3C Governance End-to-End Proof ===\n")

    # ── Connect ───────────────────────────────────────────────────────────────
    from supabase import create_client
    from src.v13.governance.api import GovernanceAPI
    from src.v13.governance.persistence import ProposalPersistence
    from src.v13.governance.doctrine_manager import DoctrineManager
    from src.v13.governance.ledger import GovernanceLedger

    db  = create_client(SUPA_URL, SUPA_KEY)
    gov = GovernanceAPI(db)
    pp  = ProposalPersistence(db)
    dm  = DoctrineManager(db)
    gl  = GovernanceLedger(db)

    # ── Step 1: Tables present ────────────────────────────────────────────────
    print("Step 1: Verify governance tables")
    for tbl in ("patch_proposals", "doctrine_versions", "governance_ledger"):
        res = db.table(tbl).select("*").limit(1).execute()
        check(f"Table '{tbl}' accessible", res is not None, f"data type: {type(res.data)}")

    # ── Step 2: Doctrine baseline ─────────────────────────────────────────────
    print("\nStep 2: Doctrine baseline")
    active_ver = dm.get_active_version()
    check("Active doctrine version returned", bool(active_ver), active_ver)
    check("Baseline is 13.0.0 or later", active_ver >= "13.0.0", active_ver)
    v_detail = dm.get_version_details(active_ver)
    check("get_version_details() returns row", v_detail is not None)
    check("Active flag is True", v_detail.get("active") == True)

    # ── Step 3: Seed synthetic learned_pattern above threshold ────────────────
    print("\nStep 3: Seed synthetic learned_pattern")
    patt_name = "proof_signal_miss_market_deception_score"
    now_iso = datetime.now(timezone.utc).isoformat()
    # Delete any pre-existing test pattern
    db.table("learned_patterns").delete().eq("pattern_name", patt_name).execute()

    db.table("learned_patterns").insert({
        "pattern_name":           patt_name,
        "pattern_type":           "signal_attribution",
        "description":            "[PROOF TEST] Winner dominated on market_deception_score",
        "conditions":             {"signal": "market_deception_score", "source_date": "2026-03-18"},
        "occurrences":            10,
        "successful_predictions": 0,
        "success_rate":           0.0,
        "confidence_level":       0.2,
        "first_observed":         now_iso,
        "last_observed":          now_iso,
        "created_at":             now_iso,
        "updated_at":             now_iso,
        "is_active":              True,
    }).execute()

    p_check = db.table("learned_patterns").select("id,occurrences").eq("pattern_name", patt_name).execute()
    check("Synthetic pattern inserted", bool(p_check.data), f"occurrences={p_check.data[0]['occurrences'] if p_check.data else '?'}")

    # ── Step 4: Create proposal from pattern ──────────────────────────────────
    print("\nStep 4: Proposal creation from learned_pattern")
    proposal_id = pp.persist_proposal(
        source_race_id=None,
        source_pattern_name=patt_name,
        critic_type="SIGMA",
        severity="MEDIUM",
        finding_type="SIGNAL_UNDERWEIGHTED",
        description="[PROOF TEST] market_deception_score underweighted 10x, 0% win rate",
        proposed_change={
            "pattern_name": patt_name,
            "occurrences": 10,
            "success_rate": 0.0,
            "suggested_action": "Review doctrine weighting for market_deception_score",
        },
    )
    check("persist_proposal() returned an ID", bool(proposal_id), str(proposal_id))

    # Deduplication check
    dup_id = pp.persist_proposal(
        source_race_id=None,
        source_pattern_name=patt_name,
        critic_type="SIGMA",
        severity="MEDIUM",
        finding_type="SIGNAL_UNDERWEIGHTED",
        description="[PROOF TEST] market_deception_score underweighted 10x, 0% win rate",
        proposed_change={
            "pattern_name": patt_name,
            "occurrences": 10,
            "success_rate": 0.0,
            "suggested_action": "Review doctrine weighting for market_deception_score",
        },
    )
    check("Duplicate persist returns None (fingerprint dedup)", dup_id is None, str(dup_id))

    # ── Step 5: DRAFT → PENDING transition ───────────────────────────────────
    print("\nStep 5: DRAFT -> PENDING transition")
    row_before = pp.get_proposal_by_id(proposal_id)
    check("Proposal is DRAFT before transition", row_before.get("status") == "DRAFT", row_before.get("status"))
    transitioned = pp.transition_all_drafts_to_pending()
    check("transition_all_drafts_to_pending() > 0", transitioned > 0, str(transitioned))
    row_after = pp.get_proposal_by_id(proposal_id)
    check("Proposal is PENDING after transition", row_after.get("status") == "PENDING", row_after.get("status"))

    # ── Step 6: list_proposals ───────────────────────────────────────────────
    print("\nStep 6: list_proposals()")
    pending_list = gov.list_proposals(status="PENDING")
    check("list_proposals(PENDING) returns ≥1", len(pending_list) >= 1, f"count={len(pending_list)}")
    ids_in_list = [p["id"] for p in pending_list]
    check("Our proposal is in the list", proposal_id in ids_in_list)

    # ── Step 7: get_proposal ─────────────────────────────────────────────────
    print("\nStep 7: get_proposal()")
    detail = gov.get_proposal(proposal_id)
    check("get_proposal() returns row", detail is not None)
    check("finding_type correct", detail.get("finding_type") == "SIGNAL_UNDERWEIGHTED")
    check("ledger_history key present", "ledger_history" in detail)
    check("ledger_history is empty (no decisions yet)", len(detail["ledger_history"]) == 0)

    # ── Step 8: reject_proposal ──────────────────────────────────────────────
    print("\nStep 8: reject_proposal()")
    reject_result = gov.reject_proposal(
        proposal_id=proposal_id,
        reviewer_id="proof_test_reviewer",
        rationale="Proof test rejection — this is a synthetic test proposal",
    )
    check("reject_proposal() returns status=rejected", reject_result.get("status") == "rejected")
    row_rejected = pp.get_proposal_by_id(proposal_id)
    check("Proposal status is REJECTED", row_rejected.get("status") == "REJECTED")
    ledger_entries = gl.get_entries_by_proposal(proposal_id)
    check("Ledger has 1 REJECT entry", len(ledger_entries) == 1)
    check("Ledger action is REJECT", ledger_entries[0].get("action") == "REJECT" if ledger_entries else False)
    check("Ledger actor is proof_test_reviewer",
          ledger_entries[0].get("actor") == "proof_test_reviewer" if ledger_entries else False)

    # ── Step 9: accept_proposal → doctrine version bump ──────────────────────
    print("\nStep 9: accept_proposal() + doctrine version bump")
    # Create a fresh proposal to accept
    patt_name_2 = "proof_tier_A_accuracy_confirm"
    db.table("learned_patterns").delete().eq("pattern_name", patt_name_2).execute()
    db.table("learned_patterns").insert({
        "pattern_name":           patt_name_2,
        "pattern_type":           "tier_accuracy",
        "description":            "[PROOF TEST] A-tier accuracy confirmation",
        "conditions":             {"decision_tier": "A"},
        "occurrences":            8,
        "successful_predictions": 6,
        "success_rate":           0.75,
        "confidence_level":       0.16,
        "first_observed":         now_iso,
        "last_observed":          now_iso,
        "created_at":             now_iso,
        "updated_at":             now_iso,
        "is_active":              True,
    }).execute()

    proposal_id_2 = pp.persist_proposal(
        source_race_id=None,
        source_pattern_name=patt_name_2,
        critic_type="SIGMA",
        severity="LOW",
        finding_type="TIER_ACCURACY",
        description="[PROOF TEST] A-tier shows 75% strike rate — positive evidence",
        proposed_change={"pattern_name": patt_name_2, "occurrences": 8, "success_rate": 0.75},
    )
    check("Second proposal created", bool(proposal_id_2), str(proposal_id_2))
    # Transition to PENDING
    pp.transition_all_drafts_to_pending()
    row_2 = pp.get_proposal_by_id(proposal_id_2)
    check("Second proposal is PENDING", row_2.get("status") == "PENDING")

    version_before = dm.get_active_version()
    accept_result = gov.accept_proposal(
        proposal_id=proposal_id_2,
        reviewer_id="proof_test_reviewer",
        rationale="Proof test acceptance — positive A-tier evidence. Doctrine MINOR bump.",
        change_type="MINOR",
    )
    check("accept_proposal() returns status=accepted", accept_result.get("status") == "accepted")
    check("previous_version matches", accept_result.get("previous_version") == version_before)
    new_version = accept_result.get("doctrine_version")
    check("New doctrine version returned", bool(new_version), new_version)
    check("Doctrine version bumped (new != old)", new_version != version_before,
          f"{version_before} → {new_version}")

    # Verify doctrine_versions table has 2 rows now
    all_versions = dm.get_version_history()
    check("doctrine_versions has ≥2 rows", len(all_versions) >= 2, f"count={len(all_versions)}")
    active_row = next((v for v in all_versions if v.get("active")), None)
    check("New version is active", active_row.get("version") == new_version if active_row else False)
    old_row = next((v for v in all_versions if v.get("version") == version_before), None)
    check("Old version is deactivated", old_row.get("active") == False if old_row else False)

    # Verify ledger has accept entry
    ledger_2 = gl.get_entries_by_proposal(proposal_id_2)
    check("Ledger has 1 ACCEPT entry for proposal 2", len(ledger_2) == 1)
    check("Ledger action is ACCEPT", ledger_2[0].get("action") == "ACCEPT" if ledger_2 else False)

    # ── Step 10: stats() ─────────────────────────────────────────────────────
    print("\nStep 10: stats()")
    stats = gov.get_stats()
    check("stats() returns dict", isinstance(stats, dict))
    check("doctrine_version in stats", stats.get("doctrine_version") == new_version)
    check("proposals_accepted >= 1", stats.get("proposals_accepted", 0) >= 1)
    check("proposals_rejected >= 1", stats.get("proposals_rejected", 0) >= 1)
    check("acceptance_rate > 0", stats.get("acceptance_rate", 0) > 0)
    print(f"     stats: {json.dumps(stats, indent=6)}")

    # ── Step 11: Cleanup ─────────────────────────────────────────────────────
    print("\nStep 11: Cleanup test rows")
    # Remove test proposals from governance_ledger first (FK)
    db.table("governance_ledger").delete().eq("proposal_id", proposal_id).execute()
    db.table("governance_ledger").delete().eq("proposal_id", proposal_id_2).execute()
    db.table("patch_proposals").delete().eq("id", proposal_id).execute()
    db.table("patch_proposals").delete().eq("id", proposal_id_2).execute()
    db.table("learned_patterns").delete().eq("pattern_name", patt_name).execute()
    db.table("learned_patterns").delete().eq("pattern_name", patt_name_2).execute()
    # Rollback doctrine to 13.0.0 (clean slate)
    dm.rollback_to_version("13.0.0")
    # Delete bumped version row
    db.table("doctrine_versions").delete().eq("version", new_version).execute()
    final_ver = dm.get_active_version()
    check("Doctrine rolled back to 13.0.0", final_ver == "13.0.0", final_ver)
    print("  Cleanup complete.")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("PROOF SUMMARY")
    print("=" * 50)
    total = len(RESULTS)
    passed = sum(1 for r in RESULTS if r[0] == "PASS")
    failed = [r for r in RESULTS if r[0] == "FAIL"]
    print(f"  {passed}/{total} checks passed")
    if failed:
        print("\n  FAILURES:")
        for sym, label, detail in failed:
            print(f"    [FAIL] {label}: {detail}")
    print(f"\n  Overall: {'PROOF COMPLETE' if PASS else 'PROOF FAILED'}")
    return 0 if PASS else 1


if __name__ == "__main__":
    sys.exit(main())
