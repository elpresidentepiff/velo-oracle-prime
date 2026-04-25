"""
VÉLØ Daily Orchestrator — laptop-first
=======================================
Runs the complete post-race pipeline for a given date in the correct order:

  1. run_results_sigma.py       scoring settlement + sigma_audits + betting_ledger
  2. close_sigma_loops.py       learned_patterns + governance proposals + Playbook G feed
  3. post_race_truth_loop.py    race_truth_audits (Layer 4)
  4. post_race_truth_loop.py    weekly rollup
  5. evolve_playbook_g_from_sigma_audits.py   G state enrichment

Verification at each step — exits non-zero if a critical step fails.

Run:
    python scripts/run_velo_daily.py --date 2026-04-11
    python scripts/run_velo_daily.py               # defaults to today
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


def _run(label: str, args: list[str], *, critical: bool = True) -> bool:
    """Run a subprocess. Print output. Return True on success."""
    print(f"\n{'='*60}")
    print(f"STEP: {label}")
    print(f"CMD:  {' '.join(args)}")
    print("="*60)
    result = subprocess.run(args, cwd=str(ROOT), env={**os.environ, "PYTHONPATH": str(ROOT)})
    ok = result.returncode == 0
    print(f"\n[{'OK' if ok else 'FAIL'}] {label} (exit {result.returncode})")
    if not ok and critical:
        print(f"\n*** CRITICAL FAILURE in {label} — aborting ***")
        sys.exit(result.returncode)
    return ok


def _verify(target_date: str) -> dict:
    """Query Supabase and return counts for all key tables."""
    db = create_client(SUPA_URL, SUPA_KEY)

    def _count(table: str, **filters) -> int:
        q = db.table(table).select("id", count="exact")
        for col, val in filters.items():
            q = q.eq(col, val)
        return q.execute().count or 0

    # velo_verdicts filtered by generated_at date prefix
    vv_rows = (db.table("velo_verdicts")
               .select("id", count="exact")
               .gte("generated_at", f"{target_date}T00:00:00")
               .lt("generated_at", f"{target_date}T23:59:59")
               .execute())
    vv = vv_rows.count or 0

    sa = _count("sigma_audits", date=target_date)
    rta = _count("race_truth_audits", race_date=target_date)

    lp_all = (db.table("learned_patterns")
              .select("id,pattern_type", count="exact")
              .gte("updated_at", f"{target_date}T00:00:00")
              .execute())
    lp = lp_all.count or 0
    lp_types = {}
    for r in (lp_all.data or []):
        t = r.get("pattern_type") or "none"
        lp_types[t] = lp_types.get(t, 0) + 1

    bl = _count("betting_ledger", date=target_date)

    # Governance proposals
    try:
        gp_rows = (db.table("learned_patterns")
                   .select("id", count="exact")
                   .like("pattern_name", f"%-proposal-%")
                   .gte("updated_at", f"{target_date}T00:00:00")
                   .execute())
        gp = gp_rows.count or 0
    except Exception:
        gp = -1

    # Race ID mismatch check
    sa_ids = {r["race_id"] for r in
              db.table("sigma_audits").select("race_id").eq("date", target_date).execute().data or []}
    rta_ids = {r["race_id"] for r in
               db.table("race_truth_audits").select("race_id").eq("race_date", target_date).execute().data or []}
    missing_truth = sa_ids - rta_ids

    return {
        "velo_verdicts": vv,
        "sigma_audits": sa,
        "race_truth_audits": rta,
        "betting_ledger": bl,
        "learned_patterns_updated": lp,
        "learned_pattern_types": lp_types,
        "governance_proposals": gp,
        "races_in_sigma_not_in_truth": sorted(missing_truth),
    }


def _print_verification(counts: dict, target_date: str) -> bool:
    """Print verification table. Return True if loop looks complete."""
    print(f"\n{'='*60}")
    print(f"VERIFICATION — {target_date}")
    print("="*60)

    rows = [
        ("velo_verdicts",          counts["velo_verdicts"],           44,  "expected ~44"),
        ("sigma_audits",           counts["sigma_audits"],            44,  "must match verdicts"),
        ("race_truth_audits",      counts["race_truth_audits"],       44,  "Layer 4 required"),
        ("betting_ledger",         counts["betting_ledger"],           0,  "B/C tier only"),
        ("learned_patterns upd",   counts["learned_patterns_updated"], 1,  "tier/miss patterns"),
        ("governance_proposals",   counts["governance_proposals"],     0,  "optional"),
    ]

    all_pass = True
    for name, actual, minimum, note in rows:
        status = "OK" if actual >= minimum else "WARN"
        if name in ("sigma_audits", "race_truth_audits") and actual != counts["velo_verdicts"]:
            status = "MISMATCH"
            all_pass = False
        print(f"  {status:7s} {name:<30s} {actual:>4d}   ({note})")

    if counts["learned_pattern_types"]:
        print(f"\n  learned_pattern types written today:")
        for pt, n in sorted(counts["learned_pattern_types"].items()):
            print(f"    {pt}: {n}")

    missing = counts["races_in_sigma_not_in_truth"]
    if missing:
        print(f"\n  WARNING: {len(missing)} races in sigma_audits but missing from race_truth_audits:")
        for r in missing[:10]:
            print(f"    {r}")
        all_pass = False

    verdict = "FULL LOOP COMPLETE" if (
        counts["velo_verdicts"] > 0
        and counts["sigma_audits"] == counts["velo_verdicts"]
        and counts["race_truth_audits"] == counts["velo_verdicts"]
        and counts["learned_patterns_updated"] > 0
    ) else "PARTIAL"

    print(f"\n  VERDICT: {verdict}")
    print("="*60)
    return verdict == "FULL LOOP COMPLETE"


def main():
    parser = argparse.ArgumentParser(description="VÉLØ Daily Orchestrator")
    parser.add_argument("--date", default=str(date.today()),
                        help="Race date YYYY-MM-DD (default: today)")
    parser.add_argument("--skip-scoring", action="store_true",
                        help="Skip run_results_sigma.py (already ran)")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only run verification, no execution")
    args = parser.parse_args()
    target_date = args.date

    print(f"\nVÉLØ DAILY ORCHESTRATOR — {target_date}")
    print(f"Started: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S UTC')}")

    if args.verify_only:
        counts = _verify(target_date)
        _print_verification(counts, target_date)
        return

    # ── Step 1: Sigma settlement ───────────────────────────────────────────────
    if not args.skip_scoring:
        _run("Sigma settlement",
             [PYTHON, "scripts/run_results_sigma.py", "--date", target_date],
             critical=True)
    else:
        print("\nSkipping sigma settlement (--skip-scoring)")

    # ── Step 2: Close sigma loops (learned patterns + governance + Playbook G) ─
    _run("Close sigma loops",
         [PYTHON, "scripts/close_sigma_loops.py", "--date", target_date],
         critical=False)   # non-critical — fallback path handles historical dates

    # ── Step 3: Layer 4 truth audit ────────────────────────────────────────────
    _run("Layer 4 truth loop",
         [PYTHON, "scripts/post_race_truth_loop.py", "--date", target_date],
         critical=False)

    # ── Step 4: Weekly rollup ─────────────────────────────────────────────────
    _run("Truth rollup",
         [PYTHON, "scripts/post_race_truth_loop.py", "--rollup", "--days", "7"],
         critical=False)

    # ── Step 5: Playbook G enrichment ─────────────────────────────────────────
    _run("Playbook G evolution",
         [PYTHON, "scripts/evolve_playbook_g_from_sigma_audits.py",
          "--dates", target_date],
         critical=False)

    # ── Verification ──────────────────────────────────────────────────────────
    counts = _verify(target_date)
    complete = _print_verification(counts, target_date)
    sys.exit(0 if complete else 1)


if __name__ == "__main__":
    main()
