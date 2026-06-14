"""
Run Decision Policy V1 against a dated New Build prediction file.

Usage:
    python scripts/ops/new_build_decision_policy_run.py --date 2026-06-03
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRED_DIR = ROOT / "data" / "new_build" / "paper_predictions"
REPORT_DIR = ROOT / "data" / "new_build" / "reports"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True)
    p.add_argument("--no-v3", action="store_true", help="Disable V3 velocity sidecar")
    args = p.parse_args()

    import sys
    sys.path.insert(0, str(ROOT))
    from new_build_velo.decision_policy_v1 import classify_predictions, lane_summary

    # Load predictions
    date_tag = args.date.replace("-", "_")
    pred_path = PRED_DIR / f"new_build_predictions_{date_tag}.jsonl"
    if not pred_path.exists():
        raise SystemExit(f"Predictions not found: {pred_path}")

    rows = [json.loads(l) for l in pred_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"Loaded {len(rows)} predictions for {args.date}")

    # Classify
    classified = classify_predictions(rows, use_v3_sidecar=not args.no_v3)
    summary = lane_summary(classified)

    # Report
    print(f"\nDecision Policy V1 — {args.date}")
    print(f"  Total runners: {summary['total']}")
    for lane, count in summary["lane_counts"].items():
        bar = "█" * count
        print(f"  {lane:<14} {count:3d}")

    print(f"\nWIN_TRUST ({len(summary['win_trust_picks'])} picks):")
    for pick in sorted(summary["win_trust_picks"], key=lambda x: x.get("off_time") or ""):
        print(f"  {pick['off_time'] or '?':5} {pick['course'] or '?':<6} {pick['horse']:<30} p={pick['prob']:.3f}  PP={pick['pp_strength']:.1f}  rank={pick['rank']}")

    print(f"\nFRAME_TRUST ({len(summary['frame_trust_picks'])} picks):")
    for pick in sorted(summary["frame_trust_picks"], key=lambda x: x.get("off_time") or ""):
        pr = f"plr={pick['place_rate_last3']:.2f}" if pick.get("place_rate_last3") is not None else "plr=n/a"
        print(f"  {pick['off_time'] or '?':5} {pick['course'] or '?':<6} {pick['horse']:<30} p={pick['prob']:.3f}  {pr}  rank={pick['rank']}")

    # Write report
    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "champion_version": "Challenger_V1",
        "policy_version": "decision_policy_v1",
        "v3_sidecar_active": not args.no_v3,
        "summary": summary,
        "classified_rows": len(classified),
    }
    rpt_path = REPORT_DIR / f"decision_policy_v1_{date_tag}.json"
    rpt_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport: {rpt_path.name}")

    # Write JSONL with lane annotations
    out_path = PRED_DIR / f"new_build_predictions_{date_tag}_policy.jsonl"
    out_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in classified),
        encoding="utf-8",
    )
    print(f"Annotated: {out_path.name}")


if __name__ == "__main__":
    main()
