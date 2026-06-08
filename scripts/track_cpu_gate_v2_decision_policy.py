#!/usr/bin/env python3
"""
CPU Gate V2 Decision Policy Tracker

Tracks decision policy evidence metrics over time for the CPU Shadow Gate V2.
Reads verdict files and sigma results from FIX_DATE (2026-05-21) onwards.
Computes SR, Brier, top-decile SR, and subgroup breakdowns.

Shadow/research only. No scoring changes. No model promotion.

Outputs:
  data/reports/cpu_gate_v2_decision_policy_tracker_latest.json
  data/reports/cpu_gate_v2_decision_policy_tracker_latest.md

Usage:
    PYTHONPATH=. python scripts/track_cpu_gate_v2_decision_policy.py
"""

from __future__ import annotations

import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIX_DATE = "2026-05-21"
GATE_1 = 150
GATE_2 = 300
BASELINE_SR = 0.20

TIER_ORDER = ["A", "B", "C", "X"]
VP_BANDS = [
    ("VP_LT_20", 0.0, 0.20),
    ("VP_20_30", 0.20, 0.30),
    ("VP_30_40", 0.30, 0.40),
    ("VP_GE_40", 0.40, 1.01),
]


def _load_decisions() -> list[dict]:
    """Load all top-pick decisions from FIX_DATE onwards."""
    decisions: list[dict] = []

    verdict_files = sorted(
        ROOT / "data",
        key=lambda f: f.name
    ) if False else sorted(
        (ROOT / "data").glob("velo_prime_verdicts_2026_05_2*.json")
    )

    for vf in verdict_files:
        # Extract date string
        import re
        m = re.search(r"(\d{4}_\d{2}_\d{2})", vf.name)
        if not m:
            continue
        date_und = m.group(1)
        date_str = date_und.replace("_", "-")
        if date_str < FIX_DATE:
            continue

        res_path = ROOT / "data" / f"results_{date_und}.json"
        if not res_path.exists():
            continue

        try:
            verdicts = json.loads(vf.read_text())
            results_raw = json.loads(res_path.read_text())
            results = results_raw.get("results", []) if isinstance(results_raw, dict) else results_raw
            result_map = {r["race_id"]: r for r in results}
        except Exception:
            continue

        for v in verdicts:
            race_id = v.get("race_id", "")
            tier = v.get("tier", "X")
            top = v.get("top", {})
            vp = float(top.get("velo_prime_prob") or 0)
            top_pick = (top.get("horse") or "").strip().lower()

            res = result_map.get(race_id)
            if not res:
                continue

            winner = next(
                (r for r in res.get("runners", []) if str(r.get("position", "")) == "1"),
                None
            )
            if not winner:
                continue

            won = (winner.get("horse", "").strip().lower() == top_pick)
            decisions.append({
                "date": date_str,
                "race_id": race_id,
                "tier": tier,
                "vp": vp,
                "won": won,
            })

    return decisions


def _compute_stats(decisions: list[dict]) -> dict:
    n = len(decisions)
    if n == 0:
        return {"n": 0}

    wins = sum(1 for d in decisions if d["won"])
    sr = round(wins / n, 4) if n > 0 else None

    # Brier score: mean((vp - outcome)^2)
    brier = round(
        sum((d["vp"] - (1 if d["won"] else 0)) ** 2 for d in decisions) / n, 4
    ) if n > 0 else None

    # Calibration baseline Brier (always predict 0.25 baseline)
    brier_baseline = round(sum((0.25 - (1 if d["won"] else 0)) ** 2 for d in decisions) / n, 4)

    # Top-decile: top 10% by VP
    sorted_by_vp = sorted(decisions, key=lambda d: d["vp"], reverse=True)
    top_decile_n = max(1, n // 10)
    top_decile = sorted_by_vp[:top_decile_n]
    top_decile_wins = sum(1 for d in top_decile if d["won"])
    top_decile_sr = round(top_decile_wins / len(top_decile), 4) if top_decile else None

    # Tier breakdown
    by_tier: dict[str, dict] = {}
    for tier in TIER_ORDER:
        subset = [d for d in decisions if d["tier"] == tier]
        if not subset:
            continue
        t_wins = sum(1 for d in subset if d["won"])
        by_tier[tier] = {
            "n": len(subset),
            "wins": t_wins,
            "sr": round(t_wins / len(subset), 4),
        }

    # VP band breakdown
    by_vp_band: dict[str, dict] = {}
    for band_name, lo, hi in VP_BANDS:
        subset = [d for d in decisions if lo <= d["vp"] < hi]
        if not subset:
            continue
        b_wins = sum(1 for d in subset if d["won"])
        by_vp_band[band_name] = {
            "n": len(subset),
            "wins": b_wins,
            "sr": round(b_wins / len(subset), 4),
        }

    # Best and worst subgroups (tier, min n=3)
    tier_srs = {t: v["sr"] for t, v in by_tier.items() if v["n"] >= 3}
    best_tier = max(tier_srs, key=tier_srs.get) if tier_srs else None
    worst_tier = min(tier_srs, key=tier_srs.get) if tier_srs else None

    return {
        "n": n,
        "wins": wins,
        "sr": sr,
        "sr_vs_baseline": round(sr - BASELINE_SR, 4) if sr is not None else None,
        "brier_score": brier,
        "brier_baseline": brier_baseline,
        "brier_skill": round(1 - brier / brier_baseline, 4) if brier and brier_baseline else None,
        "top_decile_n": top_decile_n,
        "top_decile_sr": top_decile_sr,
        "by_tier": by_tier,
        "by_vp_band": by_vp_band,
        "best_subgroup": best_tier,
        "worst_subgroup": worst_tier,
    }


def _gate_verdict(n: int) -> str:
    if n >= GATE_2:
        return "REVIEW_AT_300"
    if n >= GATE_1:
        return "REVIEW_AT_150"
    return "NEEDS_MORE_DAYS"


def _write_md(out: dict) -> str:
    stats = out["stats"]
    n = stats.get("n", 0)
    sr = stats.get("sr")
    brier = stats.get("brier_score")
    brier_skill = stats.get("brier_skill")
    top_d_sr = stats.get("top_decile_sr")
    verdict = out["verdict"]

    tier_rows = ""
    for tier, td in stats.get("by_tier", {}).items():
        tier_rows += f"| {tier} | {td['n']} | {td['wins']} | {td['sr']:.1%} | {td['sr'] - BASELINE_SR:+.1%} |\n"

    vp_rows = ""
    for band, bd in stats.get("by_vp_band", {}).items():
        vp_rows += f"| {band} | {bd['n']} | {bd['wins']} | {bd['sr']:.1%} | {bd['sr'] - BASELINE_SR:+.1%} |\n"

    date_rows = ""
    for d, ds in sorted(out.get("by_date", {}).items()):
        date_rows += f"| {d} | {ds['n']} | {ds['wins']} | {ds['sr']:.1%} |\n"

    return f"""# CPU Gate V2 Decision Policy Tracker

**Generated:** {out['generated_at']}
**FIX_DATE:** {FIX_DATE} (first clean day after a33c5bd flatline fix)
**Status:** SHADOW/RESEARCH ONLY — NOT_APPROVED

---

## Decision Policy Progress

| Metric | Value |
|---|---|
| Top-pick decisions made | **{out['decisions_made']}** |
| Decisions with outcomes | {out['decisions_with_outcomes']} |
| Excluded (no result) | {out['decisions_excluded_no_result']} |
| Wins | {stats.get('wins', 0)} |
| SR | {f"{sr:.1%}" if sr else "N/A"} |
| Baseline SR | {BASELINE_SR:.0%} |
| SR vs baseline | {f"{stats.get('sr_vs_baseline', 0):+.1%}" if stats.get('sr_vs_baseline') is not None else 'N/A'} |
| Brier score | {f"{brier:.4f}" if brier else "N/A"} |
| Brier skill score | {f"{brier_skill:.4f}" if brier_skill else "N/A"} |
| Top-decile SR (n={stats.get("top_decile_n",0)}) | {f"{top_d_sr:.1%}" if top_d_sr else "N/A"} |
| Best subgroup | {stats.get('best_subgroup','N/A')} |
| Worst subgroup | {stats.get('worst_subgroup','N/A')} |
| Needed to Gate 1 (150) | **{out['needed_to_gate_1']}** |
| Needed to Gate 2 (300) | **{out['needed_to_gate_2']}** |
| Verdict | **{verdict}** |

---

## Tier Breakdown

| Tier | n | Wins | SR | vs Baseline |
|---|---|---|---|---|
{tier_rows}
---

## VP Band Breakdown

| VP Band | n | Wins | SR | vs Baseline |
|---|---|---|---|---|
{vp_rows}
---

## By Date

| Date | n | Wins | SR |
|---|---|---|---|
{date_rows}
---

## Promotion Gate

```
Gate 1 (n=150): First review — SR, Brier, top-decile analysis. NOT automatic promotion.
Gate 2 (n=300): Full policy review. NOT automatic promotion.
Verdict:        {verdict}
Action:         ACCUMULATE_EVIDENCE — no promotion discussion until Gate 1
Production:     NOT_APPROVED (operator decision required at every gate)
```

No scoring changes. No model promotion. No live-state mutation.
"""


def _load_gate_v2_total() -> int:
    """Load total top-pick decisions count from CPU gate V2 (includes DPT-excluded)."""
    gate_path = ROOT / "data" / "reports" / "cpu_shadow_gate_v2_latest.json"
    if gate_path.exists():
        try:
            d = json.loads(gate_path.read_text())
            return d.get("decision_policy_gate", {}).get("top_pick_decisions", 0)
        except Exception:
            pass
    return 0


def main() -> None:
    print("[CPU Tracker] Loading decisions from FIX_DATE onwards...")
    decisions = _load_decisions()
    n = len(decisions)
    decisions_made = _load_gate_v2_total()
    excluded = decisions_made - n
    print(f"[CPU Tracker] {n} decisions with outcomes ({decisions_made} made, {excluded} excluded — no result)")

    stats = _compute_stats(decisions)

    # By-date breakdown
    by_date: dict[str, dict] = {}
    for d in decisions:
        date = d["date"]
        if date not in by_date:
            by_date[date] = {"n": 0, "wins": 0}
        by_date[date]["n"] += 1
        by_date[date]["wins"] += int(d["won"])
    for date, ds in by_date.items():
        ds["sr"] = round(ds["wins"] / ds["n"], 4) if ds["n"] > 0 else 0

    verdict = _gate_verdict(n)

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fix_date": FIX_DATE,
        "gate_1": GATE_1,
        "gate_2": GATE_2,
        "decisions_made": decisions_made,
        "decisions_with_outcomes": n,
        "decisions_excluded_no_result": excluded,
        "n": n,
        "needed_to_gate_1": max(0, GATE_1 - decisions_made),
        "needed_to_gate_2": max(0, GATE_2 - decisions_made),
        "verdict": verdict,
        "stats": stats,
        "by_date": by_date,
    }

    out_dir = ROOT / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "cpu_gate_v2_decision_policy_tracker_latest.json"
    md_path = out_dir / "cpu_gate_v2_decision_policy_tracker_latest.md"

    json_path.write_text(json.dumps(out, indent=2))
    print(f"[CPU Tracker] Written: {json_path}")

    md_path.write_text(_write_md(out))
    print(f"[CPU Tracker] Written: {md_path}")

    print()
    print(f"  decisions_made={decisions_made}, with_outcomes={n}, excluded={excluded}")
    print(f"  SR={stats.get('sr', 0):.1%}, Brier={stats.get('brier_score','N/A')}, top_decile_sr={stats.get('top_decile_sr', 0) or 0:.1%}")
    print(f"  needed_to_150={out['needed_to_gate_1']}, needed_to_300={out['needed_to_gate_2']}")
    print(f"  verdict={verdict}")


if __name__ == "__main__":
    main()
