#!/usr/bin/env python3
"""
Build the RPDC RS>=1.5 gate operator card for the dashboard.

Reads today's verdict file (data/velo_prime_verdicts_YYYY_MM_DD.json,
already has top.rpdc_release_score/rpdc_tags per race, attached live at
scoring time by run_prime_today.py). Advisory only -- does not change
scoring, tiers, or staking. Displays the gate's verified-clean calibration
alongside today's actual per-race values.

Usage:
    python scripts/ops/build_rpdc_gate_card.py --date YYYY-MM-DD
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "data" / "reports"

RS_GATE_THRESHOLD = 1.5

# Verified 2026-07-27 -- see docs/current/ONE_TRUTH.md Phase A-D section and
# docs/current/VELO_HARDENING_STATE.md C-3. Traced the exact dates behind
# every qualifying race against all historical rescore/backfill runs; zero
# overlap. This calibration is genuinely clean of the RPDC look-ahead leak
# found and fixed the same day in build_rpdc_daily.py.
CALIBRATION = {
    "base_rate_sr": 26.7,
    "documented_sr": 44.7,
    "documented_n": 38,
    "current_sr": 38.6,
    "current_n": 44,
    "verified_clean_of_rpdc_leak": True,
    "verified_at": "2026-07-27",
    "status": "ADVISORY — not promoted to active staking signal",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    date_tag = args.date.replace("-", "_")

    verdict_path = ROOT / "data" / f"velo_prime_verdicts_{date_tag}.json"
    if not verdict_path.exists():
        print(f"No verdict file for {args.date}: {verdict_path}")
        return

    verdicts = json.loads(verdict_path.read_text())
    races = []
    qualified_count = 0
    for race in verdicts:
        top = race.get("top") or {}
        rs = top.get("rpdc_release_score")
        rs = float(rs) if rs is not None else 0.0
        qualifies = rs >= RS_GATE_THRESHOLD
        if qualifies:
            qualified_count += 1
        races.append({
            "race_id": race.get("race_id"),
            "course": race.get("course"),
            "off_time": race.get("off_time"),
            "horse": top.get("horse"),
            "rpdc_release_score": rs,
            "rpdc_tags": top.get("rpdc_tags") or [],
            "rpdc_cash_window_flag": bool(top.get("rpdc_cash_window_flag")),
            "gate_qualified": qualifies,
            "velo_prime_prob": top.get("velo_prime_prob"),
        })

    output = {
        "date": args.date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gate_threshold": RS_GATE_THRESHOLD,
        "calibration": CALIBRATION,
        "today_races_total": len(races),
        "today_gate_qualified_count": qualified_count,
        "races": races,
    }

    out_dated = REPORTS_DIR / f"rpdc_gate_card_{date_tag}.json"
    out_latest = REPORTS_DIR / "rpdc_gate_card_latest.json"
    out_dated.write_text(json.dumps(output, indent=2))
    out_latest.write_text(json.dumps(output, indent=2))
    print(f"RPDC_GATE_CARD_COMPLETE date={args.date} races={len(races)} "
          f"qualified={qualified_count}")
    print(f"json={out_dated}")


if __name__ == "__main__":
    main()
