#!/usr/bin/env python3
"""
Race Shape Precision Tracker

Tracks precision metrics for each Race Shape flag subset over time.
Reads from the shadow ledger and outputs cumulative per-flag stats.
Designed to be run after each daily ledger update.

Shadow/research only. No scoring changes.

Outputs:
  data/reports/race_shape_precision_tracker_latest.json
  data/reports/race_shape_precision_tracker_latest.md

Usage:
    PYTHONPATH=. python scripts/track_race_shape_precision.py [--date YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LEDGER_PATH = ROOT / "data" / "reports" / "race_shape_shadow_ledger_latest.json"

GATE_1 = 150
GATE_2 = 300
PROVISIONAL_N = 5
ACTIONABLE_N = 50

SR_THRESHOLD_ACTIONABLE = 0.22
SR_THRESHOLD_BROAD = 0.30


def _flag_rows(rows: list[dict], flag: str) -> list[dict]:
    """Return rows matching the given flag name."""
    if flag == "FAV_VULN_ULTRA_COMPRESSED":
        return [r for r in rows
                if r.get("race_shape_status") == "FAV_VULNERABLE"
                and r.get("vp_spread_top3") is not None
                and r["vp_spread_top3"] < 0.01]
    if flag == "MIDPRICE_TRAP":
        return [r for r in rows if r.get("race_shape_status") == "MIDPRICE_TRAP"]
    if flag == "HIGH_COMPRESSION":
        # Stricter than COMPRESSED threshold (< 0.04): require < 0.02
        return [r for r in rows
                if r.get("vp_spread_top3") is not None
                and r["vp_spread_top3"] < 0.02]
    if flag == "FAV_VULNERABLE":
        return [r for r in rows if r.get("race_shape_status") == "FAV_VULNERABLE"]
    if flag == "CLEAR_TOP":
        return [r for r in rows if r.get("race_shape_status") == "CLEAR_TOP"]
    if flag == "CHAOTIC":
        return [r for r in rows if r.get("race_shape_status") == "CHAOTIC"]
    if flag == "SHAPE_SILENT":
        return [r for r in rows if not r.get("shape_would_warn")]
    return []


def _verdict(n: int, sr: float | None, flag: str) -> str:
    if flag == "CLEAR_TOP":
        return "NOT_USEFUL"
    if flag == "SHAPE_SILENT":
        return "BASELINE_REFERENCE"
    if n < PROVISIONAL_N:
        return "NEEDS_MORE_DATA"
    if sr is None:
        return "NEEDS_MORE_DATA"
    if n >= ACTIONABLE_N and sr <= SR_THRESHOLD_ACTIONABLE:
        return "ACTIONABLE_CANDIDATE"
    if sr <= SR_THRESHOLD_ACTIONABLE:
        return "PROVISIONAL_RISK_FLAG"
    if sr <= SR_THRESHOLD_BROAD:
        return "BROAD_WARNING_ONLY"
    return "REJECT"


def _compute_flag_stats(rows: list[dict], flag: str) -> dict:
    subset = _flag_rows(rows, flag)
    n = len(subset)

    wins = sum(1 for r in subset if r.get("outcome") == "WIN")
    misses = [r for r in subset if r.get("outcome") == "MISS"]
    n_miss = len(misses)

    sr = round(wins / n, 4) if n > 0 else None
    loss_rate = round(n_miss / n, 4) if n > 0 else None

    visible = sum(1 for r in misses if r.get("winner_visible"))
    ranked23 = sum(1 for r in misses if r.get("winner_ranked_2_or_3"))
    midprice_misses = sum(1 for r in misses if r.get("winner_in_midprice"))

    vp_gaps = [r["vp_spread_top3"] for r in subset if r.get("vp_spread_top3") is not None]
    avg_vp_spread_top3 = round(sum(vp_gaps) / len(vp_gaps), 4) if vp_gaps else None

    # Frame rate: winner was visible (in snapshot top-n) — proxy for "race was frameable"
    frame_rate = round(visible / n_miss, 4) if n_miss > 0 else None

    winner_visible_rate = round(100 * visible / n_miss, 1) if n_miss > 0 else None
    winner_ranked23_rate = round(100 * ranked23 / n_miss, 1) if n_miss > 0 else None
    midprice_miss_rate = round(100 * midprice_misses / n_miss, 1) if n_miss > 0 else None

    needed_to_gate1 = max(0, GATE_1 - n)
    needed_to_gate2 = max(0, GATE_2 - n)

    verdict = _verdict(n, sr, flag)

    return {
        "flag": flag,
        "n": n,
        "wins": wins,
        "misses": n_miss,
        "sr": sr,
        "sr_pct": f"{sr:.1%}" if sr is not None else "N/A",
        "top_pick_loss_rate": loss_rate,
        "frame_rate": frame_rate,
        "avg_vp_spread_top3": avg_vp_spread_top3,
        "winner_visible_rate_pct": winner_visible_rate,
        "winner_ranked_23_rate_pct": winner_ranked23_rate,
        "midprice_miss_rate_pct": midprice_miss_rate,
        "needed_to_gate_150": needed_to_gate1,
        "needed_to_gate_300": needed_to_gate2,
        "verdict": verdict,
    }


FLAGS = [
    "FAV_VULN_ULTRA_COMPRESSED",
    "MIDPRICE_TRAP",
    "HIGH_COMPRESSION",
    "FAV_VULNERABLE",
    "CLEAR_TOP",
    "CHAOTIC",
    "SHAPE_SILENT",
]


def run_tracker(rows: list[dict]) -> list[dict]:
    return [_compute_flag_stats(rows, flag) for flag in FLAGS]


def _write_md(stats: list[dict], n_total: int, date: str) -> str:
    header = (
        "| Flag | n | SR | Loss Rate | Frame Rate | Visible% | Ranked23% | Midprice Miss% | "
        "Avg VP Gap | To 150 | To 300 | Verdict |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|\n"
    )

    def _row(s: dict) -> str:
        fr = f"{s['frame_rate']:.1%}" if s.get("frame_rate") is not None else "N/A"
        vg = f"{s['avg_vp_spread_top3']:.4f}" if s.get("avg_vp_spread_top3") is not None else "N/A"
        lr = f"{s['top_pick_loss_rate']:.1%}" if s.get("top_pick_loss_rate") is not None else "N/A"
        vis = f"{s['winner_visible_rate_pct']}%" if s.get("winner_visible_rate_pct") is not None else "N/A"
        r23 = f"{s['winner_ranked_23_rate_pct']}%" if s.get("winner_ranked_23_rate_pct") is not None else "N/A"
        mp = f"{s['midprice_miss_rate_pct']}%" if s.get("midprice_miss_rate_pct") is not None else "N/A"
        return (
            f"| {s['flag']} | {s['n']} | {s['sr_pct']} | {lr} | {fr} | "
            f"{vis} | {r23} | {mp} | {vg} | "
            f"{s['needed_to_gate_150']} | {s['needed_to_gate_300']} | **{s['verdict']}** |\n"
        )

    table = header + "".join(_row(s) for s in stats)

    actionable = [s for s in stats if s["verdict"] in ("ACTIONABLE_CANDIDATE", "PROVISIONAL_RISK_FLAG")]
    actionable_block = ""
    if actionable:
        actionable_block = "\n**Provisional risk flags (requires 300+ corpus to confirm):**\n"
        for s in actionable:
            actionable_block += f"- {s['flag']}: n={s['n']}, SR={s['sr_pct']}, {s['needed_to_gate_150']} more to Gate 1\n"

    fuc = next((s for s in stats if s["flag"] == "FAV_VULN_ULTRA_COMPRESSED"), {})
    mt = next((s for s in stats if s["flag"] == "MIDPRICE_TRAP"), {})
    fv = next((s for s in stats if s["flag"] == "FAV_VULNERABLE"), {})
    ss = next((s for s in stats if s["flag"] == "SHAPE_SILENT"), {})

    return f"""# Race Shape Precision Tracker — {date}

**Generated:** {datetime.now(timezone.utc).isoformat()}
**Shadow ledger rows:** {n_total}
**Status:** SHADOW/RESEARCH ONLY — no scoring integration

---

## Precision Flag Tracking

{table}

Gate 1 = 150 races | Gate 2 = 300 races
ACTIONABLE_CANDIDATE requires n ≥ 50 and SR ≤ 22%
PROVISIONAL_RISK_FLAG requires n ≥ 5 and SR ≤ 22%
{actionable_block}
---

## Key Comparisons

| Pair | SR | Difference |
|---|---|---|
| FAV_VULN_ULTRA_COMPRESSED vs FAV_VULNERABLE | {fuc.get('sr_pct','N/A')} vs {fv.get('sr_pct','N/A')} | {f"{(fv.get('sr',0) or 0) - (fuc.get('sr',0) or 0):.1%}" if fuc.get('sr') and fv.get('sr') else 'N/A'} |
| FAV_VULNERABLE vs SHAPE_SILENT | {fv.get('sr_pct','N/A')} vs {ss.get('sr_pct','N/A')} | {f"{(ss.get('sr',0) or 0) - (fv.get('sr',0) or 0):.1%}" if fv.get('sr') and ss.get('sr') else 'N/A'} |
| MIDPRICE_TRAP vs ALL | {mt.get('sr_pct','N/A')} vs 25.0% | {f"{0.25 - (mt.get('sr',0) or 0):.1%}" if mt.get('sr') is not None else 'N/A'} |

---

## Corpus Progress

| Target | Current | Gate 1 (150) | Gate 2 (300) | Status |
|---|---|---|---|---|
| Total shadow ledger rows | {n_total} | 150 | 300 | {'ON_TRACK' if n_total >= 50 else 'ACCUMULATING'} |
| FAV_VULN_ULTRA_COMPRESSED | {fuc.get('n', 0)} | 50 (provisional) | 150 | {fuc.get('verdict','?')} |
| MIDPRICE_TRAP | {mt.get('n', 0)} | 20 | 50 | {mt.get('verdict','?')} |

---

## Governance

```
Shadow tracking only.
No scoring changes.
No VP adjustments.
No routing changes.
Promotion gate: operator decision required after 300+ corpus.
```
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Race Shape Precision Tracker")
    parser.add_argument("--date", default="2026-05-22", help="YYYY-MM-DD")
    args = parser.parse_args()

    if not LEDGER_PATH.exists():
        print(f"[Tracker] Ledger not found: {LEDGER_PATH}")
        print("         Run build_race_shape_shadow_ledger.py first")
        sys.exit(1)

    ledger = json.loads(LEDGER_PATH.read_text())
    rows = ledger.get("rows", [])
    print(f"[Tracker] Loaded {len(rows)} rows from shadow ledger")

    stats = run_tracker(rows)

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    out = {
        "date": args.date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ledger_rows": len(rows),
        "gate_1": GATE_1,
        "gate_2": GATE_2,
        "flags": stats,
    }

    json_path = out_dir / "race_shape_precision_tracker_latest.json"
    md_path = out_dir / "race_shape_precision_tracker_latest.md"

    json_path.write_text(json.dumps(out, indent=2))
    print(f"[Tracker] Written: {json_path}")

    md_path.write_text(_write_md(stats, len(rows), args.date))
    print(f"[Tracker] Written: {md_path}")

    print()
    for s in stats:
        print(f"  {s['flag']}: n={s['n']}, SR={s['sr_pct']}, to_150={s['needed_to_gate_150']}, verdict={s['verdict']}")


if __name__ == "__main__":
    main()
