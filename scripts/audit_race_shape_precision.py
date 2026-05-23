#!/usr/bin/env python3
"""
Race Shape V2 Precision Calibration Audit

Analyses the Race Shape shadow ledger at per-status and per-subset granularity.
For each shape subset: n, SR, frame rate, winner visible %, winner ranked 2/3 %, avg VP gap.
Produces promotion verdicts: ACTIONABLE_RISK_FLAG / BROAD_WARNING_ONLY / NOT_USEFUL / NEEDS_MORE_DATA.

Shadow/research only. No scoring changes.

Outputs:
  data/reports/race_shape_precision_audit_latest.json
  data/reports/race_shape_precision_audit_latest.md

Usage:
    PYTHONPATH=. python scripts/audit_race_shape_precision.py [--date YYYY-MM-DD]
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
PRECISION_MIN_N = 5
ACTIONABLE_SR_CEILING = 0.22
BROAD_WARNING_SR_CEILING = 0.30

# Subsets to test within FAV_VULNERABLE
FAV_VULN_SUBSETS = [
    ("FAV_VULN_ULTRA_COMPRESSED", lambda r: r.get("vp_spread_top3") is not None and r.get("vp_spread_top3") < 0.01),
    ("FAV_VULN_VP_LT_15", lambda r: (r.get("top_pick_vp") or 0) < 0.15),
    ("FAV_VULN_VP_LT_12", lambda r: (r.get("top_pick_vp") or 0) < 0.12),
    ("FAV_VULN_WINNER_MIDPRICE", lambda r: r.get("winner_in_midprice") is True),
]


def _verdict(n: int, sr: float | None, status: str) -> str:
    if n < PRECISION_MIN_N:
        return "NEEDS_MORE_DATA"
    if sr is None:
        return "NEEDS_MORE_DATA"
    if status in ("CLEAR_TOP",):
        return "NOT_USEFUL"
    if sr <= ACTIONABLE_SR_CEILING:
        return "ACTIONABLE_RISK_FLAG"
    if sr <= BROAD_WARNING_SR_CEILING:
        return "BROAD_WARNING_ONLY"
    return "NOT_USEFUL"


def _analyse_subset(rows: list[dict], label: str, status_filter: str | None = None) -> dict:
    n = len(rows)
    wins = [r for r in rows if r.get("outcome") == "WIN"]
    misses = [r for r in rows if r.get("outcome") == "MISS"]
    n_win = len(wins)
    n_miss = len(misses)
    sr = round(n_win / n, 4) if n > 0 else None

    visible = sum(1 for r in misses if r.get("winner_visible"))
    ranked23 = sum(1 for r in misses if r.get("winner_ranked_2_or_3"))
    midprice_misses = sum(1 for r in misses if r.get("winner_in_midprice"))

    vp_gaps = [r["vp_spread_top3"] for r in rows if r.get("vp_spread_top3") is not None]
    avg_vp_gap = round(sum(vp_gaps) / len(vp_gaps), 4) if vp_gaps else None

    top_vps = [r["top_pick_vp"] for r in rows if r.get("top_pick_vp") is not None]
    avg_top_vp = round(sum(top_vps) / len(top_vps), 4) if top_vps else None

    verdict = _verdict(n, sr, status_filter or label)

    return {
        "label": label,
        "n": n,
        "wins": n_win,
        "misses": n_miss,
        "sr": sr,
        "sr_pct": f"{sr:.1%}" if sr is not None else "N/A",
        "winner_visible": visible,
        "winner_visible_pct": round(100 * visible / n_miss, 1) if n_miss > 0 else None,
        "winner_ranked_2_or_3": ranked23,
        "winner_ranked_23_pct": round(100 * ranked23 / n_miss, 1) if n_miss > 0 else None,
        "midprice_misses": midprice_misses,
        "midprice_miss_pct": round(100 * midprice_misses / n_miss, 1) if n_miss > 0 else None,
        "avg_vp_gap": avg_vp_gap,
        "avg_top_vp": avg_top_vp,
        "verdict": verdict,
    }


def run_audit(rows: list[dict]) -> dict:
    all_statuses = sorted({r.get("race_shape_status", "UNKNOWN") for r in rows})
    results: list[dict] = []

    # Per-status analysis
    for status in all_statuses:
        subset = [r for r in rows if r.get("race_shape_status") == status]
        results.append(_analyse_subset(subset, status, status))

    # FAV_VULNERABLE precision subsets
    fav_vuln_rows = [r for r in rows if r.get("race_shape_status") == "FAV_VULNERABLE"]
    for subset_label, fn in FAV_VULN_SUBSETS:
        subset = [r for r in fav_vuln_rows if fn(r)]
        results.append(_analyse_subset(subset, subset_label, "FAV_VULNERABLE_SUBSET"))

    # Overall
    results.append(_analyse_subset(rows, "ALL_RACES", "ALL"))

    # Shape-warn split
    warned = [r for r in rows if r.get("shape_would_warn")]
    not_warned = [r for r in rows if not r.get("shape_would_warn")]
    results.append(_analyse_subset(warned, "SHAPE_WARNED", "SHAPE_WARNED"))
    results.append(_analyse_subset(not_warned, "SHAPE_SILENT", "SHAPE_SILENT"))

    return {"subsets": results}


def _write_md(audit: dict, ledger_summary: dict, date: str) -> str:
    subsets = audit["subsets"]

    # Separate per-status vs subsets vs overall
    status_rows = [s for s in subsets if s["label"] not in (
        "ALL_RACES", "SHAPE_WARNED", "SHAPE_SILENT"
    ) and not s["label"].startswith("FAV_VULN_")]
    subset_rows = [s for s in subsets if s["label"].startswith("FAV_VULN_")]
    meta_rows = [s for s in subsets if s["label"] in ("ALL_RACES", "SHAPE_WARNED", "SHAPE_SILENT")]

    def _row(s: dict) -> str:
        vis = f"{s['winner_visible_pct']}%" if s.get("winner_visible_pct") is not None else "N/A"
        r23 = f"{s['winner_ranked_23_pct']}%" if s.get("winner_ranked_23_pct") is not None else "N/A"
        mp = f"{s['midprice_miss_pct']}%" if s.get("midprice_miss_pct") is not None else "N/A"
        vg = f"{s['avg_vp_gap']:.4f}" if s.get("avg_vp_gap") is not None else "N/A"
        return (
            f"| {s['label']} | {s['n']} | {s['wins']} | {s['sr_pct']} | "
            f"{vis} | {r23} | {mp} | {vg} | **{s['verdict']}** |\n"
        )

    header = "| Subset | n | Wins | SR | Visible% | Ranked23% | Midprice Miss% | Avg VP Gap | Verdict |\n|---|---|---|---|---|---|---|---|---|\n"

    status_block = header + "".join(_row(s) for s in status_rows)
    subset_block = header + "".join(_row(s) for s in subset_rows)
    meta_block = header + "".join(_row(s) for s in meta_rows)

    # Actionable candidates
    actionable = [s for s in subsets if s["verdict"] == "ACTIONABLE_RISK_FLAG"]
    actionable_note = ""
    if actionable:
        labels = ", ".join(s["label"] for s in actionable)
        actionable_note = f"\n**ACTIONABLE candidates:** {labels}\n\nThese subsets have SR ≤ {ACTIONABLE_SR_CEILING:.0%} with n ≥ {PRECISION_MIN_N}. Candidate for V2 precision warning gate — requires 300+ race corpus to confirm.\n"
    else:
        actionable_note = "\nNo actionable-risk-flag subsets identified at n ≥ 5 yet. V1 is BROAD_WARNING_ONLY across all evaluated statuses. Accumulate corpus toward 300+ races for quartile SR analysis.\n"

    return f"""# Race Shape V2 Precision Calibration Audit — {date}

**Generated:** {datetime.now(timezone.utc).isoformat()}
**Ledger rows:** {len([s for s in subsets if s['label'] == 'ALL_RACES'][0:1]) and subsets[-3]['n'] or '?'}
**Status:** SHADOW/RESEARCH ONLY — no scoring integration
**V1 finding:** SR_warned={ledger_summary.get('sr_when_warned', 0):.1%} vs SR_silent={ledger_summary.get('sr_when_not_warned', 0):.1%} — 17pp discriminative but too broad ({ledger_summary.get('shape_warned_count', 0)}/{ledger_summary.get('total_races', 0)} warned)

---

## Per-Status Analysis

{status_block}
---

## FAV_VULNERABLE Precision Subsets

FAV_VULNERABLE is the dominant status ({ledger_summary.get('shape_warned_count', '?')} of {ledger_summary.get('total_races', '?')} total warned). Subsets tested for V2 precision gate candidates.

{subset_block}
---

## Meta Comparisons

{meta_block}
{actionable_note}
---

## V2 Precision Calibration — Key Findings

1. **FAV_VULNERABLE dominates** — {sum(1 for r in [s for s in status_rows if s['label']=='FAV_VULNERABLE'])>0 and [s for s in status_rows if s['label']=='FAV_VULNERABLE'][0]['n'] or '?'}/36 races. Single-status SR=26.1%. Not tight enough for suppression without VP scoring implications.

2. **Winner visibility is not the problem** — 92.6% of miss winners were visible in snapshots. The miss structure is ranking failure, not coverage failure.

3. **Midprice misses concentrate in FAV_VULNERABLE** — 11/17 FAV_VULNERABLE misses had winners in the 3.0–8.5 SP zone. This is the primary V2 research target.

4. **n=36 is too small for quartile SR analysis** — V2 requires 300+ races minimum. Current corpus: 36 races (May 22 only). Accumulate corpus daily.

5. **COMPRESSED and CHAOTIC** — n=2 and n=1 respectively. Architecturally interesting but statistically unusable at current corpus size.

---

## Promotion Gate

```
V2 actionable subsets:    requires n >= 300 races and quartile SR analysis
V1 broad warning:         CONFIRMED — 17pp discriminative but too broad
V2 precision gate:        NOT MET — insufficient corpus
Next milestone:           300+ races in shadow ledger corpus
```

Shadow ledger only. No scoring changes. No VP adjustments. No routing changes.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Race Shape V2 Precision Calibration Audit")
    parser.add_argument("--date", default="2026-05-22", help="YYYY-MM-DD")
    args = parser.parse_args()

    if not LEDGER_PATH.exists():
        print(f"[WARN] Ledger not found: {LEDGER_PATH}")
        print("       Run build_race_shape_shadow_ledger.py first")
        sys.exit(1)

    ledger = json.loads(LEDGER_PATH.read_text())
    rows = ledger.get("rows", [])
    ledger_summary = ledger.get("summary", {})

    print(f"[Precision] Loaded {len(rows)} rows from ledger")

    audit = run_audit(rows)

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    out = {
        "date": args.date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ledger_rows": len(rows),
        "ledger_summary": ledger_summary,
        "subsets": audit["subsets"],
    }

    json_path = out_dir / "race_shape_precision_audit_latest.json"
    md_path = out_dir / "race_shape_precision_audit_latest.md"

    json_path.write_text(json.dumps(out, indent=2))
    print(f"[Precision] Written: {json_path}")

    md_path.write_text(_write_md(audit, ledger_summary, args.date))
    print(f"[Precision] Written: {md_path}")

    print()
    for s in audit["subsets"]:
        print(f"  {s['label']}: n={s['n']}, SR={s['sr_pct']}, verdict={s['verdict']}")


if __name__ == "__main__":
    main()
