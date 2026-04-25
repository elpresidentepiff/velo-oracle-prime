"""
VÉLØ Full Feedback Loop Orchestrator — laptop-first
====================================================
Runs the complete VÉLØ cycle in the correct order:

  1.  score_card          run_prime_today.py --date (score + persist verdicts)
  2.  settle_sigma        run_results_sigma.py --date (sigma_audits + betting_ledger)
  3.  truth_audit         post_race_truth_loop.py --date (race_truth_audits)
  4.  truth_rollup        post_race_truth_loop.py --rollup --days 7
  5.  close_sigma_loops   close_sigma_loops.py --date
                            → learned_patterns
                            → patch_proposals (descriptive + actionable)
                            → playbook_g feed
  6.  apply_proposals     apply_approved_proposals.py
                            → reads APPROVED proposals
                            → writes runtime_overrides (ACTIVE)
  7.  evolve_playbook_g   evolve_playbook_g_from_sigma_audits.py --dates
  8.  verify              count rows across all key tables

Output:
  Plain-English FULL LOOP COMPLETE / PARTIAL verdict
  Exact row counts for every table in the loop
  Mismatch report if sigma_audits ≠ velo_verdicts

Flags:
  --date YYYY-MM-DD     target date (default: today)
  --skip-scoring        skip Step 1 (already ran run_prime_today.py)
  --skip-sigma          skip Step 2 (already ran run_results_sigma.py)
  --from-step N         start from step N (1-8), skipping earlier steps
  --verify-only         skip all execution, just run verification
  --dry-run-proposals   pass --dry-run to apply_approved_proposals.py

Run:
  python scripts/run_full_feedback_loop.py --date 2026-04-11
  python scripts/run_full_feedback_loop.py               # defaults to today
  python scripts/run_full_feedback_loop.py --verify-only
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

SUPA_URL = os.getenv("SUPABASE_URL", "")
SUPA_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY", ""))

PYTHON = sys.executable


# ── Step runner ───────────────────────────────────────────────────────────────

def _run(step_num: int, label: str, args: list[str], *,
         critical: bool = True, start_from: int = 1) -> bool:
    """Run a subprocess. Print label + cmd + exit status. Return True on success."""
    if step_num < start_from:
        print(f"\n[SKIP] Step {step_num}: {label} (--from-step {start_from})")
        return True

    print(f"\n{'='*60}")
    print(f"STEP {step_num}: {label}")
    print(f"CMD:  {' '.join(args)}")
    print("="*60)
    result = subprocess.run(
        args,
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    ok = result.returncode == 0
    print(f"\n[{'OK' if ok else 'FAIL'}] {label} (exit {result.returncode})")

    if not ok and critical:
        print(f"\n*** CRITICAL FAILURE in {label} — aborting ***")
        sys.exit(result.returncode)
    return ok


# ── Verification ──────────────────────────────────────────────────────────────

def _verify(target_date: str) -> dict:
    """Query Supabase and return counts for all key tables in the loop."""
    db = create_client(SUPA_URL, SUPA_KEY)

    def _count(table: str, **filters) -> int:
        q = db.table(table).select("id", count="exact")
        for col, val in filters.items():
            q = q.eq(col, val)
        return q.execute().count or 0

    # velo_verdicts — filtered by generated_at date prefix
    vv = (
        db.table("velo_verdicts")
        .select("id", count="exact")
        .gte("generated_at", f"{target_date}T00:00:00")
        .lt("generated_at", f"{target_date}T23:59:59")
        .execute()
    ).count or 0

    sa  = _count("sigma_audits",      date=target_date)
    rta = _count("race_truth_audits", race_date=target_date)
    bl  = _count("betting_ledger",    date=target_date)

    # learned_patterns updated today
    lp_rows = (
        db.table("learned_patterns")
        .select("id, pattern_type", count="exact")
        .gte("updated_at", f"{target_date}T00:00:00")
        .execute()
    )
    lp = lp_rows.count or 0
    lp_types: dict = {}
    for r in (lp_rows.data or []):
        t = r.get("pattern_type") or "none"
        lp_types[t] = lp_types.get(t, 0) + 1

    # patch_proposals
    pp_all = (
        db.table("patch_proposals")
        .select("id, status, finding_type", count="exact")
        .gte("created_at", f"{target_date}T00:00:00")
        .execute()
    )
    pp = pp_all.count or 0
    pp_by_status: dict = {}
    pp_actionable = 0
    for r in (pp_all.data or []):
        s = r.get("status") or "UNKNOWN"
        pp_by_status[s] = pp_by_status.get(s, 0) + 1
        if r.get("finding_type") in (
            "TIER_THRESHOLD_ADJUSTMENT", "PROMOTION_BLOCKER_RULE", "TRAP_ESCALATION_RULE"
        ):
            pp_actionable += 1

    # runtime_overrides active count
    ovr_active = (
        db.table("runtime_overrides")
        .select("id", count="exact")
        .eq("status", "ACTIVE")
        .execute()
    ).count or 0

    ovr_rows = (
        db.table("runtime_overrides")
        .select("override_key, status, updated_at")
        .eq("status", "ACTIVE")
        .execute()
    ).data or []
    ovr_keys = [r["override_key"] for r in ovr_rows]

    # Race ID mismatch: sigma_audits vs velo_verdicts
    sa_ids = {
        r["race_id"] for r in
        db.table("sigma_audits").select("race_id").eq("date", target_date).execute().data or []
    }
    vv_ids = {
        r["race_id"] for r in
        db.table("velo_verdicts")
        .select("race_id")
        .gte("generated_at", f"{target_date}T00:00:00")
        .lt("generated_at", f"{target_date}T23:59:59")
        .execute().data or []
    }
    missing_sigma = vv_ids - sa_ids   # verdicts with no sigma audit
    extra_sigma   = sa_ids - vv_ids   # sigma audits with no verdict

    # Race ID mismatch: race_truth_audits vs velo_verdicts
    rta_ids = {
        r["race_id"] for r in
        db.table("race_truth_audits").select("race_id").eq("race_date", target_date).execute().data or []
    }
    missing_truth = vv_ids - rta_ids

    return {
        "velo_verdicts":          vv,
        "sigma_audits":           sa,
        "race_truth_audits":      rta,
        "betting_ledger":         bl,
        "learned_patterns_today": lp,
        "learned_pattern_types":  lp_types,
        "patch_proposals_today":  pp,
        "patch_proposals_by_status": pp_by_status,
        "actionable_proposals":   pp_actionable,
        "runtime_overrides_active": ovr_active,
        "active_override_keys":   ovr_keys,
        "verdicts_without_sigma": sorted(missing_sigma),
        "verdicts_without_truth": sorted(missing_truth),
        "sigma_without_verdict":  sorted(extra_sigma),
    }


def _print_verification(counts: dict, target_date: str) -> bool:
    """Print the verification table. Return True if loop is fully complete."""
    print(f"\n{'='*60}")
    print(f"VERIFICATION — {target_date}")
    print("="*60)

    vv  = counts["velo_verdicts"]
    sa  = counts["sigma_audits"]
    rta = counts["race_truth_audits"]

    rows = [
        ("velo_verdicts",          vv,                              44,  "expected ~44 UK/IRE races"),
        ("sigma_audits",           sa,                              44,  "must equal verdicts"),
        ("race_truth_audits",      rta,                             44,  "Layer 4 required"),
        ("betting_ledger",          counts["betting_ledger"],         0,  "B/C tier only (may be 0)"),
        ("learned_patterns today",  counts["learned_patterns_today"], 1,  "tier/miss patterns"),
        ("patch_proposals today",   counts["patch_proposals_today"],  0,  "descriptive + actionable"),
        ("actionable_proposals",    counts["actionable_proposals"],   0,  "override candidates"),
        ("runtime_overrides active",counts["runtime_overrides_active"],0, "active scoring overrides"),
    ]

    all_pass = True
    for name, actual, minimum, note in rows:
        if name in ("sigma_audits", "race_truth_audits") and vv > 0 and actual != vv:
            status = "MISMATCH"
            all_pass = False
        elif actual >= minimum:
            status = "OK"
        else:
            status = "WARN"
        print(f"  {status:8s} {name:<32s} {actual:>4d}   ({note})")

    # Learned pattern types
    if counts["learned_pattern_types"]:
        print(f"\n  learned_pattern types updated today:")
        for pt, n in sorted(counts["learned_pattern_types"].items()):
            print(f"    {pt}: {n}")

    # Proposal status breakdown
    if counts["patch_proposals_by_status"]:
        print(f"\n  patch_proposal status breakdown:")
        for st, n in sorted(counts["patch_proposals_by_status"].items()):
            print(f"    {st}: {n}")

    # Active override keys
    if counts["active_override_keys"]:
        print(f"\n  active runtime_overrides:")
        for k in counts["active_override_keys"]:
            print(f"    {k}")
    else:
        print(f"\n  runtime_overrides: NONE ACTIVE — hardcoded thresholds apply")

    # Mismatch details
    if counts["verdicts_without_sigma"]:
        print(f"\n  WARNING: {len(counts['verdicts_without_sigma'])} verdicts missing sigma_audit:")
        for r in counts["verdicts_without_sigma"][:5]:
            print(f"    {r}")
        all_pass = False

    if counts["verdicts_without_truth"]:
        print(f"\n  WARNING: {len(counts['verdicts_without_truth'])} verdicts missing truth_audit:")
        for r in counts["verdicts_without_truth"][:5]:
            print(f"    {r}")
        all_pass = False

    # Overall verdict
    feedback_live = counts["runtime_overrides_active"] > 0
    loop_complete = (
        vv > 0
        and sa == vv
        and rta == vv
        and counts["learned_patterns_today"] > 0
    )

    if loop_complete and feedback_live:
        verdict = "FULL LOOP COMPLETE + FEEDBACK ACTIVE"
    elif loop_complete:
        verdict = "FULL LOOP COMPLETE (feedback inactive — no ACTIVE overrides)"
    elif vv > 0 and sa > 0:
        verdict = "PARTIAL — scoring + sigma ran, truth/learning incomplete"
    else:
        verdict = "PARTIAL — scoring incomplete"

    print(f"\n  VERDICT: {verdict}")
    print("="*60)
    return loop_complete


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="VÉLØ Full Feedback Loop Orchestrator"
    )
    parser.add_argument("--date", default=str(date.today()),
                        help="Race date YYYY-MM-DD (default: today)")
    parser.add_argument("--skip-scoring", action="store_true",
                        help="Skip Step 1 (run_prime_today.py)")
    parser.add_argument("--skip-sigma", action="store_true",
                        help="Skip Step 2 (run_results_sigma.py)")
    parser.add_argument("--from-step", type=int, default=1,
                        help="Start from step N (1-8)")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only run verification — no execution")
    parser.add_argument("--dry-run-proposals", action="store_true",
                        help="Pass --dry-run to apply_approved_proposals.py")
    args = parser.parse_args()
    target_date = args.date
    start_from  = args.from_step

    print(f"\nVÉLØ FULL FEEDBACK LOOP — {target_date}")
    print(f"Started: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S UTC')}")

    if args.verify_only:
        counts = _verify(target_date)
        _print_verification(counts, target_date)
        return

    # ── Step 1: Score card (run_prime_today.py) ────────────────────────────────
    if not args.skip_scoring:
        _run(1, "Score card",
             [PYTHON, "scripts/run_prime_today.py", "--date", target_date],
             critical=True, start_from=start_from)
    else:
        print(f"\n[SKIP] Step 1: Score card (--skip-scoring)")

    # ── Step 2: Sigma settlement (run_results_sigma.py) ───────────────────────
    if not args.skip_sigma:
        _run(2, "Sigma settlement",
             [PYTHON, "scripts/run_results_sigma.py", "--date", target_date],
             critical=True, start_from=start_from)
    else:
        print(f"\n[SKIP] Step 2: Sigma settlement (--skip-sigma)")

    # ── Step 3: Layer 4 truth audit ───────────────────────────────────────────
    _run(3, "Layer 4 truth audit",
         [PYTHON, "scripts/post_race_truth_loop.py", "--date", target_date],
         critical=False, start_from=start_from)

    # ── Step 4: Weekly truth rollup ───────────────────────────────────────────
    _run(4, "Truth rollup (7 days)",
         [PYTHON, "scripts/post_race_truth_loop.py", "--rollup", "--days", "7"],
         critical=False, start_from=start_from)

    # ── Step 5: Close sigma loops (learning + proposals + Playbook G) ─────────
    _run(5, "Close sigma loops",
         [PYTHON, "scripts/close_sigma_loops.py", "--date", target_date],
         critical=False, start_from=start_from)

    # ── Step 6: Apply approved proposals → runtime_overrides ─────────────────
    apply_args = [PYTHON, "scripts/apply_approved_proposals.py"]
    if args.dry_run_proposals:
        apply_args.append("--dry-run")
    _run(6, "Apply approved proposals",
         apply_args,
         critical=False, start_from=start_from)

    # ── Step 7: Playbook G evolution ──────────────────────────────────────────
    _run(7, "Playbook G evolution",
         [PYTHON, "scripts/evolve_playbook_g_from_sigma_audits.py",
          "--dates", target_date],
         critical=False, start_from=start_from)

    # ── Step 8: Verification ──────────────────────────────────────────────────
    counts = _verify(target_date)
    complete = _print_verification(counts, target_date)
    sys.exit(0 if complete else 1)


if __name__ == "__main__":
    main()
