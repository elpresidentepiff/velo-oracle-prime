"""
VÉLØ Race Truth Backfill
=========================
Recomputes canonical performance metrics from raw truth sources.

What this does:
  1. Normalize all historical sigma_audits rows to WIN/PLACED/MISS/NO_RESULT
  2. Normalize all historical pipeline_runs rows to PASS/DEGRADED/FAIL
  3. Produce a console + JSON report of tier performance for the window
  4. Spot-check 10 random races to verify truth table consistency

This script does NOT modify scoring — it only reads and normalises persisted data.

Usage:
    python scripts/backfill_race_truth.py --days 60
    python scripts/backfill_race_truth.py --days 30 --dry-run
"""
import sys
import os
import json
import random
import argparse
import urllib.request
from datetime import datetime, timedelta, date
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

LEGACY_SCRIPT_STATUS = "QUARANTINED_WAVE_1"
LEGACY_SCRIPT_OWNER = "TBD"
LEGACY_EXECUTION_ENV = "VELO_LEGACY_ALLOW_BACKFILL_RACE_TRUTH"
SB_URL = os.getenv("SUPABASE_URL", "")
SB_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY", "")
SB_HEADERS = {
    "apikey":        SB_KEY,
    "Authorization": f"Bearer {SB_KEY}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}


# ── Legacy vocab mappings (one-time normalisation) ────────────────────────────

OUTCOME_MAP = {
    "HIT":     "WIN",
    "FRAME":   "PLACED",
    "WIN":     "WIN",       # already canonical
    "PLACED":  "PLACED",    # already canonical
    "MISS":    "MISS",
    "NO_RESULT": "NO_RESULT",
}

STATUS_MAP = {
    "completed":   "PASS",
    "passed":      "PASS",
    "success":     "PASS",   # legacy from workers/daily_pipeline.py
    "PASS":        "PASS",
    "partial":     "DEGRADED",
    "DEGRADED":    "DEGRADED",
    "failed":      "FAIL",
    "FAIL":        "FAIL",
    "abandoned":   "FAIL",      # lifecycle state → terminal FAIL
    "in_progress": "DEGRADED",  # incomplete run → terminal DEGRADED
}


def sb_get(path: str) -> list:
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1{path}",
        headers={**SB_HEADERS, "Prefer": ""},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def sb_patch(path: str, data: dict) -> bool:
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{SB_URL}/rest/v1{path}",
        data=body,
        headers=SB_HEADERS,
        method="PATCH",
    )
    try:
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as e:
        print(f"  [PATCH FAIL] {path}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=60)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report changes without writing them")
    args = parser.parse_args()

    since = (date.today() - timedelta(days=args.days)).isoformat()
    dry = args.dry_run
    mode = "DRY RUN" if dry else "LIVE"

    print(f"\nVELO RACE TRUTH BACKFILL — last {args.days} days — {mode}")
    print("=" * 60)

    if not SB_URL or not SB_KEY:
        print("ABORT: SUPABASE_URL or key env vars missing")
        sys.exit(1)

    # ── 1. Normalise sigma_audits outcomes ────────────────────────────────────
    print("\nSTEP 1: Normalise sigma_audits.outcome")

    sigma_rows = sb_get(
        f"/sigma_audits?select=id,outcome,decision_tier"
        f"&date=gte.{since}"
        f"&order=date.desc"
        f"&limit=2000"
    )
    print(f"  Fetched {len(sigma_rows)} sigma_audits rows since {since}")

    from src.constants import VALID_OUTCOMES, VALID_TIERS

    sigma_updates = 0
    sigma_rejects = 0
    sigma_ok      = 0
    for row in sigma_rows:
        raw = (row.get("outcome") or "").strip()
        canon = OUTCOME_MAP.get(raw)
        if canon is None:
            print(f"  [UNKNOWN] sigma id={row['id']} outcome='{raw}' — cannot map, skipping")
            sigma_rejects += 1
            continue
        if raw == canon:
            sigma_ok += 1
            continue
        # Needs normalisation
        print(f"  [NORMALISE] sigma id={row['id']}: '{raw}' -> '{canon}'")
        if not dry:
            ok = sb_patch(f"/sigma_audits?id=eq.{row['id']}", {"outcome": canon})
            if ok:
                sigma_updates += 1
            else:
                sigma_rejects += 1
        else:
            sigma_updates += 1

    print(f"  Already canonical: {sigma_ok}")
    print(f"  Normalised:        {sigma_updates}")
    print(f"  Cannot map:        {sigma_rejects}")

    # ── 2. Normalise pipeline_runs.status ─────────────────────────────────────
    print("\nSTEP 2: Normalise pipeline_runs.status")

    run_rows = sb_get(
        f"/pipeline_runs?select=id,status,started_at"
        f"&started_at=gte.{since}T00:00:00"
        f"&order=started_at.desc"
        f"&limit=500"
    )
    print(f"  Fetched {len(run_rows)} pipeline_runs rows since {since}")

    run_updates = 0
    run_rejects = 0
    run_ok      = 0
    for row in run_rows:
        raw = (row.get("status") or "").strip()
        canon = STATUS_MAP.get(raw)
        if canon is None:
            print(f"  [UNKNOWN] run id={row['id']} status='{raw}' — cannot map, skipping")
            run_rejects += 1
            continue
        if raw == canon:
            run_ok += 1
            continue
        print(f"  [NORMALISE] run id={row['id']} ({row.get('started_at','')}): '{raw}' -> '{canon}'")
        if not dry:
            ok = sb_patch(f"/pipeline_runs?id=eq.{row['id']}", {"status": canon})
            if ok:
                run_updates += 1
            else:
                run_rejects += 1
        else:
            run_updates += 1

    print(f"  Already canonical: {run_ok}")
    print(f"  Normalised:        {run_updates}")
    print(f"  Cannot map:        {run_rejects}")

    # ── 3. Recompute tier performance from canonical data ─────────────────────
    print("\nSTEP 3: Tier performance from canonical sigma_audits data")

    # Re-fetch after normalisation
    canonical_rows = sb_get(
        f"/sigma_audits?select=outcome,decision_tier,date"
        f"&date=gte.{since}"
        f"&outcome=in.(WIN,PLACED,MISS,NO_RESULT)"
        f"&limit=5000"
    )
    print(f"  Canonical rows: {len(canonical_rows)}")

    tiers: dict = {}
    for row in canonical_rows:
        tier = (row.get("decision_tier") or "?").upper()
        outcome = row.get("outcome", "")
        if tier not in tiers:
            tiers[tier] = {"WIN": 0, "PLACED": 0, "MISS": 0, "NO_RESULT": 0, "total": 0}
        tiers[tier]["total"] += 1
        if outcome in tiers[tier]:
            tiers[tier][outcome] += 1

    print(f"\n  TIER PERFORMANCE — last {args.days} days")
    print(f"  {'Tier':<6} {'Total':>6} {'WIN':>6} {'WIN%':>7} {'PLACED':>8} {'PLACE%':>8} {'MISS':>6}")
    print(f"  {'-'*55}")
    for tier in sorted(tiers):
        d = tiers[tier]
        scored = d["WIN"] + d["PLACED"] + d["MISS"]
        wp = d["WIN"]    / scored * 100 if scored else 0
        pp = (d["WIN"] + d["PLACED"]) / scored * 100 if scored else 0
        print(f"  {tier:<6} {d['total']:>6} {d['WIN']:>6} {wp:>6.1f}% {d['WIN']+d['PLACED']:>8} {pp:>7.1f}% {d['MISS']:>6}")

    # ── 4. Spot check 10 random races ─────────────────────────────────────────
    print("\nSTEP 4: Spot check 10 random reconciled races")

    reconciled = [r for r in canonical_rows if r.get("outcome") in ("WIN", "PLACED", "MISS")]
    sample = random.sample(reconciled, min(10, len(reconciled)))

    print(f"  {'date':<12} {'tier':<6} {'outcome':<10}")
    print(f"  {'-'*30}")
    for r in sorted(sample, key=lambda x: x.get("date", "")):
        print(f"  {r.get('date','?'):<12} {(r.get('decision_tier') or '?'):<6} {r.get('outcome','?'):<10}")

    # ── 5. Summary ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"BACKFILL COMPLETE — {mode}")
    print(f"  sigma_audits normalised: {sigma_updates}  (rejects: {sigma_rejects})")
    print(f"  pipeline_runs normalised: {run_updates}  (rejects: {run_rejects})")
    print(f"  canonical sigma rows:    {len(canonical_rows)}")
    print(f"  tiers with data:         {list(tiers.keys())}")
    if dry:
        print("\n  DRY RUN — no writes performed. Remove --dry-run to apply.")

    # Write JSON report
    report = {
        "generated_at":  datetime.utcnow().isoformat() + "Z",
        "mode":          mode,
        "window_days":   args.days,
        "since":         since,
        "sigma_normalised": sigma_updates,
        "sigma_rejects":    sigma_rejects,
        "run_normalised":   run_updates,
        "run_rejects":      run_rejects,
        "tier_performance": tiers,
    }
    out = ROOT / "data" / f"backfill_report_{date.today().isoformat()}.json"
    try:
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(report, indent=2))
        print(f"\n  Report saved: {out.name}")
    except Exception as e:
        print(f"\n  Report save skipped: {e}")


if __name__ == "__main__":
    if os.getenv(LEGACY_EXECUTION_ENV) != "1":
        raise SystemExit(
            "Legacy script is quarantined and blocked by default. "
            f"Set {LEGACY_EXECUTION_ENV}=1 for an intentional run."
        )
    main()
